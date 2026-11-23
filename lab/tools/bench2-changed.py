#!/usr/bin/env python3
"""After a change of the sources: which records of benchmark version 2 does
the tree no longer build, and what has to be run again for them?

Usage: lab/tools/bench2-changed.py [--rebuild] [LEDGER]

  LEDGER     a file written by lab/tools/image-ledger.py (default:
             records/rebuilt.json of this tree)
  --rebuild  make the ledger first, from what is committed at HEAD, into
             LEDGER (default then: a temporary file). About half a minute
             per board, in the toolchain image; no board is touched.

A record stands as long as the tree builds its eight images byte for byte
at the same addresses (DECISIONS 2026-11-22). So after a change of one
library only that library's configurations are measured again: this tool
names them per board, the bundles that hold their images (one flash write
each) and the commands. The other configurations of a bundle are not run
again: their images are the same bytes at the same place.

The bundle numbers are those of the records' own runs. If a changed image
no longer fits its slot, oneslots.py gives the configuration new slots and
the build says which bundle holds them.

Exit: 0 nothing to run again, 1 something to run again, 2 no answer (no
ledger, or one that was made from other sources than HEAD's).
"""
import glob
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("public_export", os.path.join(HERE, "public-export.py"))
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)
BENCH = "firmware/nrf5340-rb-bench"


def main():
    args = sys.argv[1:]
    rebuild = "--rebuild" in args
    args = [a for a in args if a != "--rebuild"]
    if len(args) > 1 or any(a.startswith("-") for a in args):
        sys.exit(__doc__)
    path = args[0] if args else os.path.join(ROOT, pe.LEDGER)
    if rebuild:
        if not args:
            path = os.path.join(tempfile.mkdtemp(prefix="vl-changed."), "rebuilt.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "image-ledger.py"), "--out", path], stdout=subprocess.DEVNULL)
        if r.returncode not in (0, 1):
            return 2
    recs = {}   # board -> {adapter: record}
    for f in sorted(glob.glob(os.path.join(ROOT, pe.V2_RECORDS, "*", "*.json"))):
        recs.setdefault(os.path.basename(os.path.dirname(f)), {})[os.path.basename(f)[:-5]] = json.load(open(f))
    led = json.load(open(path)) if os.path.exists(path) else None
    if led is not None and led.get("sources") != pe.source_ids("HEAD")[0]:
        print(f"{path} was made from other test sources than those of HEAD: make it again (--rebuild, or lab/tools/image-ledger.py)")
        return 2
    total = writes = full = 0
    plan = []
    for board in sorted(recs):
        again, unknown = {}, []
        bundles_all = set()
        for adapter, rec in sorted(recs[board].items()):
            bundles = {r["bundle"] for im in rec["images"] for r in im["runs"]}
            bundles_all |= bundles
            if pe.same_sources(rec["bench_commit"]) or pe.host_fixed(rec["bench_commit"]):
                continue
            e = (led or {}).get("records", {}).get(f"bench-v2/{board}/{adapter}.json")
            if e is None or e.get("images_sha256") != pe.v2_images_digest(rec) or e.get("result") == "not checked":
                unknown.append(adapter)
            elif e["result"] != "match":
                again[adapter] = (bundles, rec["passes"])
        full += len(bundles_all)
        if unknown:
            print(f"{board}: {len(unknown)} records without a rebuild from these sources ({', '.join(unknown[:4])}"
                  f"{' ...' if len(unknown) > 4 else ''}): --rebuild")
            return 2
        if not again:
            print(f"{board}: all {len(recs[board])} records stand")
            continue
        bundles = sorted(set().union(*(b for b, _ in again.values())))
        passes = max(p for _, p in again.values())
        total += len(again)
        writes += len(bundles)
        print(f"{board}: {len(again)} of {len(recs[board])} records to measure again: {', '.join(again)}")
        print(f"  bundle{'s' if len(bundles) > 1 else ''} {', '.join(map(str, bundles))} of {len(bundles_all)}: "
              f"{len(bundles)} flash write{'s' if len(bundles) > 1 else ''}")
        plan.append(f"BUNDLE={','.join(map(str, bundles))} bash onebuild.sh table {board}\n"
                    f"python3 run-one.py {board} $OUT/{board} --bundle {','.join(map(str, bundles))} --flash "
                    f"--passes {passes} --adapter {','.join(again)}")
    if not total:
        print("nothing to run again")
        return 0
    print(f"\n{total} records to measure again, {writes} flash writes (a full series: {full}). On lib-lab1, with the change committed:\n")
    print(f"cd {BENCH}; OUT=$HOME/lab-runs/v2-$(date -u +%Y%m%dT%H%M%SZ)")
    print("\n".join(plan))
    print("python3 onerecords.py $OUT/*      # replaces the records of these configurations only")
    print("bash oneverify.sh ../../records/bench-v2/*/*.json; then site/gen_libdata.py, site/results_tables.py")
    return 1


if __name__ == "__main__":
    sys.exit(main())
