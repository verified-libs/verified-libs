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

--all   rebuild every record with an image checksum, also those the
        export takes without one, but for archived series, which
        the tree is not meant to build (a check of the whole tree; about
        20 seconds per record, half a minute per board for version 2)
--out   write there instead of records/rebuilt.json

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

LINE = re.compile(r"^(\S+): (MATCH|DIFFERS)\s+(?:record [0-9a-f]{64}, rebuilt )?([0-9a-f]{64})\s+\((.*)\)(.*)$")


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, check=True, text=True).stdout


def main():
    args = sys.argv[1:]
    every = "--all" in args
    args = [a for a in args if a != "--all"]
    out = os.path.join(ROOT, pe.LEDGER)
    if args[:1] == ["--out"] and len(args) == 2:
        out = os.path.abspath(args[1])
    elif args:
        sys.exit(__doc__)
    head = git("rev-parse", "HEAD").strip()
    work = tempfile.mkdtemp(prefix="vl-ledger.")
    try:
        arch = pe.archived()

        def passes(c):
            """the export takes a record of commit c without a rebuild: the tree's sources,
            those but for recorded host fixes, or an archived series"""
            return pe.same_sources(c) or pe.host_fixed(c) or c[:12] in arch
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
            if not all(passes(c) for c in commits) or (every and not all(c[:12] in arch for c in commits)):
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
            if not passes(rec["bench_commit"]) or (every and rec["bench_commit"][:12] not in arch):
                name = f[len("records/"):]
                todo2[name] = pe.v2_images_digest(rec)
                os.makedirs(os.path.dirname(os.path.join(work, name)), exist_ok=True)
                with open(os.path.join(work, name), "w") as fh:
                    fh.write(text)
        if not todo and not todo2:
            print("nothing to rebuild: every record with an image checksum is one the export takes as it is (the sources of HEAD, a recorded host fix, or an archived series)")
            if os.path.exists(out):
                print(f"({out} exists; the export takes it only if it was made from these sources)")
            return 0
        env = dict(os.environ, VL_TREE="1", VL_REPO=ROOT, TMPDIR=work)
        libs = os.path.join(ROOT, "firmware/nrf5340-rb-bench/build/libs")
        if "VL_LIBS_FROM" not in env and os.path.isdir(libs):
            env["VL_LIBS_FROM"] = libs
        print(f"rebuilding {len(todo) + len(todo2)} records from the sources of {head[:12]}", flush=True)
        records, last = {}, None
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
        led = {"about": "Rebuilds of the records of other commits from this tree's test sources "
                        "(lab/tools/image-ledger.py, DECISIONS 2026-11-22). match: the tree builds, byte for byte, "
                        "the image the record was measured from.",
               "commit": head, "sources": pe.source_ids("HEAD")[0],
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
