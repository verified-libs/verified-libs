#!/usr/bin/env python3
"""Rebuild the published records of other commits from this tree and write
down which images the tree still builds: records/rebuilt.json.

Usage: lab/tools/image-ledger.py [--all] [--out FILE] [--plan] [--test-cache]

A record under records/ may be shown although its commit has other test
sources than the tree, if the tree builds the image it was measured from
(method.html#log-2026-11-22-same-image). This tool makes that check for every record under
records/bench and records/stress (as committed at HEAD) that has an image
checksum and names a commit with other test sources than HEAD (recorded
host fixes and archived series aside, as in the export): it runs
lab/tools/verify-build.sh with VL_TREE=1 on it (a build in the record's
toolchain image; no board is touched) and writes the results, with a
checksum of the test sources they were built from. public-export.py reads
the file and takes it only for the tree it was made from.

The records of benchmark version 2 (records/bench-v2) are rebuilt board by
board with firmware/nrf5340-rb-bench/oneverify.sh (VL_TREE=1): all eight
images of a record, their addresses, the fixed part and the boot stub must
be the record's. Their entries are named by path (bench-v2/<board>/<file>)
and hold one checksum over all of that (images_sha256).

The records of the CRC kind (records/crc) are rebuilt with
kinds/crc/bench/crcverify.sh (VL_TREE=1), board by board, if their commit
has other CRC test sources than HEAD (recorded host fixes aside) and their
host side stands (public-export.py, crc_host_stands; DECISIONS
2026-11-24): the same comparisons as for version 2, and the toolchain image
and the layout. Their entries are named crc/<board>/<file> and hold
crc_images_digest; the ledger holds the checksum of the CRC test sources it
was made from (sources_crc) beside that of the ring buffers' (sources). The
libraries are copied from VL_CRC_LIBS_FROM (default ~/vl-next/kind-crc, if
there) before they are fetched.
The records of the pools kind (records/pools) are held the same way, with
kinds/pools/bench/poolverify.sh, entries pools/<board>/<file> and the
checksum of the pools test sources (sources_pools); libraries from
VL_POOLS_LIBS_FROM (default ~/vl-next/kind-pools).
The records of the pools concurrency series (records/pools-isr) too, with
kinds/pools-isr/bench/isrverify.sh, entries pools-isr/<board>/<file> held
by isr_images_digest and the checksum of that kind's test sources
(sources_pools-isr); libraries as the pools kind's.
A kind of public-export.py's KINDS is rebuilt only if it has a check of a
record (its "verify" there, with its libraries' place in KIND_LIBS here);
the records of a kind without one are not rebuilt (a line says how many),
and the export stops them: the ledger never holds one. Each kind's records
are held by the kind's own checksum (KINDS "digest"; the pools concurrency
series: public-export.py isr_images_digest); a record without the fields
for it is not rebuilt either.

--all   rebuild every record with an image checksum, also those the
        export takes without one, but for archived series, which
        the tree is not meant to build (a check of the whole tree; about
        20 seconds per record, half a minute per board for version 2)
--out   write there instead of records/rebuilt.json
--test-cache  for lab/tools/test-public-export.sh only: take rebuild results
        from the cache VL_LEDGER_CACHE=DIR and keep new ones there (class
        Cache: the key covers everything a rebuild reads). Without the flag a
        set VL_LEDGER_CACHE is refused; a ledger made with it says so
        ("cache_used"), and the export and our publishing script refuse it.
--plan  only say what would be rebuilt, each record with the checksum
        its ledger entry would hold; nothing is built or written (seconds:
        the quick export test runs it)

VL_LIB_MIRROR=DIR: fetch the libraries from that local mirror only
(lab/tools/lib-mirror.py; it must hold every pin, or nothing is rebuilt), not
from the network. A rebuild whose library fetch failed is "not checked" with
a note that begins "could not fetch the libraries", never "differs": a
network fault is not a record that this tree builds another image of.

With nothing to rebuild, no file is written. Commit the file with the
records: the export reads it from HEAD.
Exit: 0 written (or nothing to do), 1 a record could not be checked.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("public_export", os.path.join(HERE, "public-export.py"))
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)
spec = importlib.util.spec_from_file_location("lib_mirror", os.path.join(HERE, "lib-mirror.py"))
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)

# per kind of pe.KINDS with a check of a record (its "verify", run with VL_TREE=1): where its libraries are copied
# from. A kind of KINDS without "verify" is not rebuilt; one with a "verify" but no entry here is an error.
KIND_LIBS = {"crc": ("VL_CRC_LIBS_FROM", "~/vl-next/kind-crc"), "pools": ("VL_POOLS_LIBS_FROM", "~/vl-next/kind-pools"),
             "pools-isr": ("VL_POOLS_LIBS_FROM", "~/vl-next/kind-pools")}
KIND_VERIFY = {k: (v["verify"], *KIND_LIBS[k]) for k, v in pe.KINDS.items() if v.get("verify")}
# a fetch of the libraries that failed, in the note of a record "not checked" (git's own words, and the verify scripts')
FETCH_FAULT = re.compile(r"could not be fetched|could not fetch|fatal: early EOF|fetch-pack|could not read from remote|"
                         r"Could not resolve host|unable to access|transport '\w+' not allowed|remote end hung up|"
                         r"RPC failed|not our ref|couldn't find remote ref|Connection (?:timed out|reset|refused)", re.I)
LINE = re.compile(r"^(\S+): (MATCH|DIFFERS)\s+(?:record [0-9a-f]{64}, rebuilt )?([0-9a-f]{64})\s+\((.*)\)(.*)$")


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, check=True, text=True).stdout


# at most this many verify scripts at once (each builds in containers of its own; the memory cap of a test holds two)
LEDGER_JOBS = 2


def parse_images(prefix, field):
    """the parser of a kind's verify script (crcverify.sh, poolverify.sh, isrverify.sh) or of version 2's
    oneverify.sh: their lines "<board>/<file>: MATCH|DIFFERS  ...", the indented lines that say why, and
    "<board>/<file>: <why not checked>"; record names are PREFIX<board>/<file>.json"""
    def parse(lines, mine):
        got, last = {}, None
        for line in lines:
            m = re.match(r"^(\S+): (MATCH|DIFFERS)  (.*)$", line)
            name = prefix + m.group(1) + ".json" if m else None
            if name in mine:
                last = name
                got[last] = {field: mine[last], "result": "match" if m.group(2) == "MATCH" else "differs"}
                if "ELF file differs" in m.group(3):
                    got[last]["note"] = m.group(3).rsplit("; ", 1)[-1]
            elif line.startswith("  ") and last in mine and not line.startswith("  kept:"):
                got[last]["note"] = "; ".join(filter(None, [got[last].get("note"), line.strip()]))
            else:
                m = re.match(r"^(\S+): (.*)$", line)
                if m and prefix + m.group(1) + ".json" in mine:
                    last = prefix + m.group(1) + ".json"
                    got[last] = {field: mine[last], "result": "not checked", "note": m.group(2)}
        return got
    return parse


def parse_fw(lines, mine):
    """the parser of verify-build.sh (the ring buffers' records of version 1)"""
    got, last = {}, None
    for line in lines:
        m = LINE.match(line)
        if m:
            last = m.group(1) + ".json"
            got[last] = {"fw_sha256": mine[last], "result": "match" if m.group(2) == "MATCH" else "differs",
                         "rebuilt_sha256": m.group(3), "toolchain_image": m.group(4).rsplit(", ", 1)[-1]}
            if m.group(5).strip():
                got[last]["note"] = m.group(5).strip()
            continue
        m = re.match(r"^  library (\S+): image differs$", line)
        if m and last:
            got[last].setdefault("libs_differ", []).append(m.group(1))
            continue
        m = re.match(r"^(\S+): (.*)$", line)
        if m and m.group(1) + ".json" in mine:
            last = m.group(1) + ".json"
            got[last] = {"fw_sha256": mine[last], "result": "not checked", "note": m.group(2)}
    return got


class Cache:
    """A cache of rebuild results for the export test's clones (--test-cache, VL_LEDGER_CACHE=DIR), never for
    the project's ledger: a record's result ("match" or "differs" only; never "not checked") is kept under a
    key of everything its rebuild reads:
      - the group (a kind of public-export.py's KINDS, bench-v2, the ring buffers) and its verify script;
      - the record file's bytes;
      - the files at HEAD under the group's test sources, all of them (every side, the files public-export.py
        leaves out of the checksum too), and under firmware/ (the board layer, the boot stub, version 2's
        programs the kinds import), toolchain/, and the lab files of TEST_SOURCES;
      - every pin of the lock files (lab/tools/lib-mirror.py pins());
      - the toolchain images on the host (podman: each verified-libs/toolchain tag and its image ID);
      - this file's own bytes.
    An entry holds its key; one that does not (a file put under another key) is not used, and is counted."""

    def __init__(self, d):
        self.dir = os.path.abspath(d)
        os.makedirs(self.dir, exist_ok=True)
        self.refused, self._trees = 0, {}
        r = subprocess.run(["podman", "images", "--no-trunc", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("--test-cache: podman could not list the toolchain images: no cache")
        images = sorted(l for l in r.stdout.splitlines() if "verified-libs/toolchain" in l)
        self.base = hashlib.sha256(json.dumps(
            [open(os.path.abspath(__file__), "rb").read().hex(), [list(p) for p in lm.pins()], images]).encode()).hexdigest()

    def tree(self, group):
        if group not in self._trees:
            paths = (pe.KINDS[group]["sources"] if group in pe.KINDS else pe.TEST_SOURCES) + ["firmware", "toolchain"] + pe.TEST_SOURCES[1:]
            self._trees[group] = hashlib.sha256(git("ls-tree", "-r", "HEAD", "--", *sorted(set(paths))).encode()).hexdigest()
        return self._trees[group]

    def key(self, group, script, rec_bytes):
        return hashlib.sha256(json.dumps([self.base, group, os.path.relpath(script, ROOT), self.tree(group),
                                          hashlib.sha256(rec_bytes).hexdigest()]).encode()).hexdigest()

    def get(self, key):
        f = os.path.join(self.dir, key[:2], key + ".json")
        if not os.path.exists(f):
            return None
        try:
            e = json.load(open(f))
        except (OSError, ValueError):
            e = None
        if not isinstance(e, dict) or e.get("key") != key or e.get("entry", {}).get("result") not in ("match", "differs"):
            self.refused += 1
            return None
        return e["entry"]

    def put(self, key, entry):
        if entry.get("result") not in ("match", "differs"):
            return
        d = os.path.join(self.dir, key[:2])
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, f".{key}.{os.getpid()}")
        with open(tmp, "w") as fh:
            json.dump({"key": key, "entry": entry}, fh)
        os.replace(tmp, os.path.join(d, key + ".json"))


def main():
    args = sys.argv[1:]
    every, plan, test_cache = "--all" in args, "--plan" in args, "--test-cache" in args
    args = [a for a in args if a not in ("--all", "--plan", "--test-cache")]
    # the cache is for the export test's clones only: never without the test's own flag, never the flag alone
    if os.environ.get("VL_LEDGER_CACHE") and not test_cache:
        sys.exit("VL_LEDGER_CACHE is set: refused (the cache is for lab/tools/test-public-export.sh's clones only, "
                 "with --test-cache; the project's ledger is made without it)")
    if test_cache and not os.environ.get("VL_LEDGER_CACHE"):
        sys.exit("--test-cache without VL_LEDGER_CACHE=DIR")
    cache = Cache(os.environ["VL_LEDGER_CACHE"]) if test_cache else None
    out = os.path.join(ROOT, pe.LEDGER)
    if args[:1] == ["--out"] and len(args) == 2:
        out = os.path.abspath(args[1])
    elif args:
        sys.exit(__doc__)
    head = git("rev-parse", "HEAD").strip()
    work = tempfile.mkdtemp(prefix="vl-ledger.")
    try:
        arch = pe.archived()

        def archived_rec(c, name):
            """the record (its path under records/) belongs to an archived series of commit c: an entry
            of the commit that covers its path (an entry with "paths" covers only those, as in the export)"""
            return any(pe.under(name, e) for e in arch.get(c[:12], []))

        def passes(c, name):
            """the export takes a record of commit c without a rebuild: the tree's sources,
            those but for recorded host fixes, or an archived series that covers it"""
            return pe.same_sources(c) or pe.host_fixed(c) or archived_rec(c, name)
        todo = {}   # file name -> fw_sha256
        for f in git("ls-tree", "-r", "--name-only", "HEAD", "--", "records/bench", "records/stress").split("\n"):
            if not f.endswith(".json"):
                continue
            text = git("show", f"HEAD:{f}")
            sha = re.search(r'"fw_sha256":\s*"([0-9a-f]{64})"', text)
            if not sha:
                continue
            commits = set()
            for one, many in pe.RECORD_COMMIT.findall(text):
                commits.update([one] if one else re.findall(r"[0-9a-f]{12,40}", many))
            rel = f[len("records/"):]
            if not all(passes(c, rel) for c in commits) or (every and not all(archived_rec(c, rel) for c in commits)):
                name = os.path.basename(f)
                if name in todo:
                    sys.exit(f"{name}: two records of that name")
                todo[name] = sha.group(1)
                with open(os.path.join(work, name), "w") as fh:
                    fh.write(text)
        todo2 = {}   # bench-v2/<board>/<file> -> checksum over the record's images
        for f in git("ls-tree", "-r", "--name-only", "HEAD", "--", pe.V2_RECORDS.rstrip("/")).split("\n"):
            if not f.endswith(".json"):
                continue
            text = git("show", f"HEAD:{f}")
            rec = json.loads(text)
            rel = f[len("records/"):]
            if not passes(rec["bench_commit"], rel) or (every and not archived_rec(rec["bench_commit"], rel)):
                name = f[len("records/"):]
                todo2[name] = pe.v2_images_digest(rec)
                os.makedirs(os.path.dirname(os.path.join(work, name)), exist_ok=True)
                with open(os.path.join(work, name), "w") as fh:
                    fh.write(text)
        todo3 = {}   # <kind>/<board>/<file> -> checksum over the record's images, for every kind of pe.KINDS
        for kind, kv in pe.KINDS.items():
            no_check, no_digest = [], []
            for f in git("ls-tree", "-r", "--name-only", "HEAD", "--", kv["records"].rstrip("/")).split("\n"):
                if not f.endswith(".json"):
                    continue
                text = git("show", f"HEAD:{f}")
                rec = json.loads(text)
                c = rec.get("bench_commit") or "unknown"
                if archived_rec(c, f[len("records/"):]):
                    continue                         # an archived series: the tree is not meant to build it
                same = pe.source_ids(c, kind)[0] is not None and pe.source_ids(c, kind)[0] == pe.source_ids("HEAD", kind)[0]
                if every or (not same and not pe.crc_host_fixed(c, kind) and pe.crc_host_stands(c, kind)):
                    name = f[len("records/"):]
                    digest = pe.kind_digest(rec, kind)
                    if kind not in KIND_VERIFY:
                        no_check.append(name)
                        continue
                    if digest is None:
                        no_digest.append(name)
                        continue
                    todo3[name] = digest
                    os.makedirs(os.path.dirname(os.path.join(work, name)), exist_ok=True)
                    with open(os.path.join(work, name), "w") as fh:
                        fh.write(text)
            if no_check:
                print(f"{len(no_check)} {kv['name']} records not rebuilt: the kind has no check of a record "
                      f"(the export stops them)", flush=True)
            if no_digest:
                print(f"{len(no_digest)} {kv['name']} records not rebuilt: without the fields of the kind's image "
                      f"checksum (the export stops them): {', '.join(no_digest[:8])}", flush=True)
        if plan:
            for n, d in sorted({**todo, **todo2, **todo3}.items()):
                print(f"would rebuild {n} {d}")
            print(f"would rebuild {len(todo) + len(todo2) + len(todo3)} records from the sources of {head[:12]} "
                  f"(--plan: nothing built or written)")
            return 0
        if not todo and not todo2 and not todo3:
            print("nothing to rebuild: every record with an image checksum is one the export takes as it is (the sources of HEAD, a recorded host fix, or an archived series)")
            if os.path.exists(out):
                print(f"({out} exists; the export takes it only if it was made from these sources)")
            return 0
        env = dict(os.environ, VL_TREE="1", VL_REPO=ROOT, TMPDIR=work)
        env.pop("VL_LEDGER_CACHE", None)   # the verify scripts never see the cache
        if os.environ.get("VL_LIB_MIRROR"):
            mirror = os.path.abspath(os.path.expanduser(os.environ["VL_LIB_MIRROR"]))
            bad = lm.check(mirror, lm.pins())
            if bad:
                print("\n".join(bad), file=sys.stderr)
                sys.exit(f"could not fetch the libraries: the mirror {mirror} lacks {len(bad)} pins; nothing rebuilt")
            env.update(lm.env(mirror, lm.pins()))
        libs = os.path.join(ROOT, "firmware/nrf5340-rb-bench/build/libs")
        if "VL_LIBS_FROM" not in env and os.path.isdir(libs):
            env["VL_LIBS_FROM"] = libs
        print(f"rebuilding {len(todo) + len(todo2) + len(todo3)} records from the sources of {head[:12]}", flush=True)
        records = {}
        # the jobs: (group, its records name -> checksum, the script, its environment, the parser of its output)
        jobs = []
        for kind, (script, libs_var, libs_default) in KIND_VERIFY.items():
            mine_k = {n: d for n, d in todo3.items() if n.startswith(kind + "/")}
            if not mine_k:
                continue
            env3 = dict(env)
            env3.pop("VL_LIBS_FROM", None)
            libs3 = os.environ.get(libs_var, os.path.expanduser(libs_default))
            if os.path.isdir(libs3):
                env3["VL_LIBS_FROM"] = libs3
            # a verify script names a record by its last two parts (<board>/<file>): the records of a kind under
            # a deeper directory (records/pools-isr/b301/<board>/<file>.json, bundle 301) go in a job of their
            # own, so that no two records of one job have the same name (the controls of bundles 300 and 301)
            subs = {}
            for n, d in mine_k.items():
                subs.setdefault("/".join(n.split("/")[:-2]) + "/", {})[n] = d
            for prefix, mine in sorted(subs.items()):
                jobs.append((kind, mine, os.path.join(ROOT, script), env3, parse_images(prefix, "images_sha256")))
        if todo2:
            jobs.append(("bench-v2", todo2, os.path.join(ROOT, "firmware/nrf5340-rb-bench/oneverify.sh"), env,
                         parse_images("bench-v2/", "images_sha256")))
        if todo:
            jobs.append(("ring buffers", todo, os.path.join(HERE, "verify-build.sh"), env, parse_fw))
        stats = {}
        if cache:
            for i, (group, mine, script, env_j, parse) in enumerate(jobs):
                miss = {}
                for n, d in mine.items():
                    e = cache.get(cache.key(group, script, open(os.path.join(work, n), "rb").read()))
                    if e is not None:
                        records[n] = e
                    else:
                        miss[n] = d
                h0, m0 = stats.get(group, (0, 0))   # a kind may have several jobs (a deeper directory)
                stats[group] = (h0 + len(mine) - len(miss), m0 + len(miss))
                jobs[i] = (group, miss, script, env_j, parse)
            print("cache (" + cache.dir + "): " + "; ".join(f"{g} {h} from the cache, {m} to rebuild" for g, (h, m) in stats.items())
                  + (f"; {cache.refused} entries refused (not of their key)" if cache.refused else ""), flush=True)
            jobs = [j for j in jobs if j[1]]

        def run(job):
            group, mine, script, env_j, _ = job
            t0 = time.time()
            p = subprocess.run(["bash", script, *[os.path.join(work, n) for n in sorted(mine)]],
                               stdout=subprocess.PIPE, text=True, env=env_j)
            return p.stdout.splitlines(), time.time() - t0
        # at most LEDGER_JOBS verify scripts at once, each in its own trees; their output is read in a fixed order
        with ThreadPoolExecutor(max_workers=LEDGER_JOBS) as pool:
            done = [pool.submit(run, j) for j in jobs]
            for (group, mine, script, env_j, parse), fut in zip(jobs, done):
                out_lines, secs = fut.result()
                print("\n".join(out_lines), flush=True)
                print(f"({group}: {len(mine)} records, {os.path.basename(script)}, {secs:.0f} s)", flush=True)
                got = parse(out_lines, mine)
                for n in mine:
                    got.setdefault(n, {**({"fw_sha256": mine[n]} if parse is parse_fw else {"images_sha256": mine[n]}),
                                       "result": "not checked", "note": f"no result from {os.path.basename(script)}"})
                records.update(got)
                if cache:
                    for n in mine:
                        cache.put(cache.key(group, script, open(os.path.join(work, n), "rb").read()), got[n])
        for r in records.values():
            if r["result"] == "not checked" and FETCH_FAULT.search(r.get("note", "")) \
                    and not r["note"].startswith("could not fetch the libraries"):
                r["note"] = "could not fetch the libraries: " + r["note"]
        led = {"about": "Rebuilds of the records of other commits from this tree's test sources "
                        "(lab/tools/image-ledger.py, DECISIONS 2026-11-22). match: the tree builds, byte for byte, "
                        "the image the record was measured from.",
               "commit": head, "sources": pe.source_ids("HEAD")[0],
               **{f"sources_{k}": pe.source_ids("HEAD", k)[0] for k in pe.KINDS},
               "records": {n: records[n] for n in sorted(records)}}
        if cache:
            led["cache_used"] = {"dir": cache.dir, "hits_and_rebuilt": stats,
                                 "note": "made with --test-cache for a test; never to be committed to the project"}
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as fh:
            json.dump(led, fh, indent=1)
            fh.write("\n")
        count = {}
        for r in records.values():
            count[r["result"]] = count.get(r["result"], 0) + 1
        print(f"{out}: " + ", ".join(f"{v} {k}" for k, v in sorted(count.items())))
        return 1 if count.get("not checked") else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
