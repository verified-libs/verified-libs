#!/usr/bin/env python3
"""Rebuild the published records of other commits from this tree and write
down which images the tree still builds: records/rebuilt.json.

Usage: lab/tools/image-ledger.py [--all] [--out FILE]

A record under records/ may be shown although its commit has other test
sources than the tree, if the tree builds the image it was measured from
(DECISIONS 2026-11-22). This tool makes that check for every record under
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
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

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


def main():
    args = sys.argv[1:]
    every, plan = "--all" in args, "--plan" in args
    args = [a for a in args if a not in ("--all", "--plan")]
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
        records, last = {}, None
        for kind, (script, libs_var, libs_default) in KIND_VERIFY.items():
            mine = {n: d for n, d in todo3.items() if n.startswith(kind + "/")}
            if not mine:
                continue
            env3 = dict(env)
            env3.pop("VL_LIBS_FROM", None)
            libs3 = os.environ.get(libs_var, os.path.expanduser(libs_default))
            if os.path.isdir(libs3):
                env3["VL_LIBS_FROM"] = libs3
            p = subprocess.Popen(["bash", os.path.join(ROOT, script), *[os.path.join(work, n) for n in sorted(mine)]],
                                 stdout=subprocess.PIPE, text=True, env=env3)
            last = None
            for line in p.stdout:
                line = line.rstrip("\n")
                print(line, flush=True)
                m = re.match(r"^(\S+): (MATCH|DIFFERS)  (.*)$", line)
                name = f"{kind}/" + m.group(1) + ".json" if m else None
                if name in mine:
                    last = name
                    records[last] = {"images_sha256": mine[last], "result": "match" if m.group(2) == "MATCH" else "differs"}
                    if "ELF file differs" in m.group(3):
                        records[last]["note"] = m.group(3).rsplit("; ", 1)[-1]
                elif line.startswith("  ") and last in mine and not line.startswith("  kept:"):
                    records[last]["note"] = "; ".join(filter(None, [records[last].get("note"), line.strip()]))
                else:
                    m = re.match(r"^(\S+): (.*)$", line)
                    if m and f"{kind}/" + m.group(1) + ".json" in mine:
                        last = f"{kind}/" + m.group(1) + ".json"
                        records[last] = {"images_sha256": mine[last], "result": "not checked", "note": m.group(2)}
            p.wait()
            for n in mine:
                records.setdefault(n, {"images_sha256": mine[n], "result": "not checked",
                                       "note": f"no result from {os.path.basename(script)}"})
            last = None
        if todo2:
            p = subprocess.Popen(["bash", os.path.join(ROOT, "firmware/nrf5340-rb-bench/oneverify.sh"),
                                  *[os.path.join(work, n) for n in sorted(todo2)]], stdout=subprocess.PIPE, text=True, env=env)
            for line in p.stdout:
                line = line.rstrip("\n")
                print(line, flush=True)
                m = re.match(r"^(\S+): (MATCH|DIFFERS)  (.*)$", line)
                name = "bench-v2/" + m.group(1) + ".json" if m else None
                if name in todo2:
                    last = name
                    records[last] = {"images_sha256": todo2[last], "result": "match" if m.group(2) == "MATCH" else "differs"}
                    if "ELF file differs" in m.group(3):
                        records[last]["note"] = m.group(3).rsplit("; ", 1)[-1]
                elif line.startswith("  ") and last in todo2 and not line.startswith("  kept:"):
                    records[last]["note"] = "; ".join(filter(None, [records[last].get("note"), line.strip()]))
                else:
                    m = re.match(r"^(\S+): (.*)$", line)
                    if m and "bench-v2/" + m.group(1) + ".json" in todo2:
                        last = "bench-v2/" + m.group(1) + ".json"
                        records[last] = {"images_sha256": todo2[last], "result": "not checked", "note": m.group(2)}
            p.wait()
            for n in todo2:
                records.setdefault(n, {"images_sha256": todo2[n], "result": "not checked", "note": "no result from oneverify.sh"})
            last = None
        p = subprocess.Popen(["bash", os.path.join(HERE, "verify-build.sh"), *[os.path.join(work, n) for n in sorted(todo)]],
                             stdout=subprocess.PIPE, text=True, env=env) if todo else None
        for line in (p.stdout if p else ()):
            line = line.rstrip("\n")
            print(line, flush=True)
            m = LINE.match(line)
            if m:
                last = m.group(1) + ".json"
                records[last] = {"fw_sha256": todo[last], "result": "match" if m.group(2) == "MATCH" else "differs",
                                 "rebuilt_sha256": m.group(3), "toolchain_image": m.group(4).rsplit(", ", 1)[-1]}
                if m.group(5).strip():
                    records[last]["note"] = m.group(5).strip()
                continue
            m = re.match(r"^  library (\S+): image differs$", line)
            if m and last:
                records[last].setdefault("libs_differ", []).append(m.group(1))
                continue
            m = re.match(r"^(\S+): (.*)$", line)
            if m and m.group(1) + ".json" in todo:
                last = m.group(1) + ".json"
                records[last] = {"fw_sha256": todo[last], "result": "not checked", "note": m.group(2)}
        if p:
            p.wait()
        for n in todo:
            records.setdefault(n, {"fw_sha256": todo[n], "result": "not checked", "note": "no result from verify-build.sh"})
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
