#!/usr/bin/env python3
"""Recompute the sweep coverage of a stress record with today's decode.py.

Usage: recompute_coverage.py RECORD.json [--tree DIR] [--out OUT.json]

The record keeps the raw coverage bitmap (sweep.bitmap_hex, since
2026-11-12) but not the listing it was mapped onto. This rebuilds the
record's firmware from the source tree DIR (default: this repository; check
it out at the record's source_commit first), in a temporary copy, with the
record's board, code location, flags, compiler and toolchain image, and
refuses unless the new fw.elf has the record's fw_sha256. Then it maps the
bitmap with decode.sweep_coverage and prints the summary; with --out it
writes a copy of the record whose sweep.functions are replaced and which
notes the recomputation (sweep.coverage_recomputed). Needs podman and the
toolchain image named in the record.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from decode import sweep_coverage   # noqa: E402

FW_BOARD = {1: "nrf5340", 2: "stm32g0b1", 3: "stm32g474", 4: "stm32h723", 5: "samd20", 6: "rp2350"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("record")
    ap.add_argument("--tree", default=os.path.dirname(os.path.dirname(HERE)),
                    help="source tree (repository root) to rebuild from")
    ap.add_argument("--out")
    a = ap.parse_args()
    with open(a.record) as fh:
        rec = json.load(fh)
    sw = rec.get("sweep")
    per_lib = (rec.get("images") or {}).get("kind") == "per_library"
    if not sw or ("bitmap_hex" not in sw and "per_library" not in sw):
        sys.exit("record has no sweep.bitmap_hex (sweep records from 2026-11-12 on)")
    hexbits = lambda h: [int(h[i:i + 8], 16) for i in range(0, len(h), 8)]
    if not per_lib:
        bits = hexbits(sw["bitmap_hex"])
        base = int(sw["coverage_base"], 16)
    p = rec["params"]
    board = FW_BOARD[p["board_id"]]
    want = rec.get("fw_sha256")
    img = rec.get("toolchain_image", "verified-libs/toolchain:2026-11-05")
    print(f"record: {os.path.basename(a.record)}; source_commit {rec.get('source_commit', 'not recorded')}; "
          f"tree {subprocess.run(['bash', os.path.join(a.tree, 'lab/tools/source-commit.sh'), a.tree], capture_output=True, text=True).stdout.strip()}")

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(a.tree, "firmware"), os.path.join(tmp, "firmware"), symlinks=True,
                        ignore=shutil.ignore_patterns("*.o", "fw.*", ".board", "flash", "sram", "ccm", "itcm"))
        libs = os.path.join(tmp, "firmware/nrf5340-rb-bench/build/libs")
        if not os.path.isdir(libs):   # e.g. a git worktree: take the fetched libraries from this repository
            shutil.copytree(os.path.join(HERE, "../nrf5340-rb-bench/build/libs"), libs, symlinks=True)
        # as run.sh: fetch-libs.sh first (it also generates build/gen/, e.g. micoring's config)
        f = subprocess.run(["bash", os.path.join(tmp, "firmware/nrf5340-rb-bench/fetch-libs.sh")],
                           capture_output=True, text=True)
        if f.returncode:
            sys.exit(f"fetch-libs.sh failed in the copy: {f.stderr.strip()[-300:]}")
        margs = (f"BOARD={board} CODE={rec['code_location']} OPT='{rec['opt']}' "
                 f"LTO={1 if rec['lto'] else 0} COMPILER={rec['compiler_libs']} EXTRA='{rec['build_flags']}'")
        if per_lib:   # as run.sh IMAGES=per_lib
            sel = ("--sel-addr " + rec["images"]["select_addr"] if board == "rp2350"
                   else "--sel-symbol results --sel-from-end 16")
            cmd = (f"mkdir -p build; make clean >/dev/null; mkdir -p build; python3 -I ../common/bundle.py "
                   f"--libs 0-{len(rec['libs']) - 1} {sel} -- {margs}")
        else:
            cmd = f"mkdir -p build; make clean >/dev/null; mkdir -p build; make {margs}"
        r = subprocess.run(["podman", "run", "--rm", "-v", f"{tmp}/firmware:/work:Z", "-w", "/work/nrf5340-rb-stress",
                            img, "sh", "-c", cmd + " >build/log.txt 2>&1; echo rc=$?"],
                           capture_output=True, text=True)
        build = os.path.join(tmp, "firmware/nrf5340-rb-stress/build")
        if "rc=0" not in r.stdout:
            sys.exit(f"rebuild failed ({r.stdout.strip()}); see the build log in a manual run")
        with open(os.path.join(build, "bundle.json" if per_lib else "fw.elf"), "rb") as fh:
            got = hashlib.sha256(fh.read()).hexdigest()
        if got != want:
            sys.exit(f"rebuilt {'bundle.json' if per_lib else 'fw.elf'} differs from the record (sha256 {got[:12]} vs {str(want)[:12]}): "
                     "wrong tree or commit, or a different toolchain image")
        if per_lib:   # each library from its own image (decode.py --images)
            from decode import LIBS
            funcs = []
            for e in sw["per_library"]:
                l = LIBS.index(e["library"])
                d = os.path.join(build, f"lib{l}")
                funcs += [{"library": e["library"], **f} for f in
                          sweep_coverage(hexbits(e["bitmap_hex"]), int(e["coverage_base"], 16),
                                         os.path.join(d, "fw.lst"), os.path.join(d, "fw.map"))]
        else:
            funcs = sweep_coverage(bits, base, os.path.join(build, "fw.lst"), os.path.join(build, "fw.map"))

    tot = sum(f["instructions"] - f["masked"] - f["probably_masked"] for f in funcs)
    hit = sum(f["interrupted"] for f in funcs)
    full = sum(1 for f in funcs if not f["not_interrupted"])
    old = {(f.get("library"), f["function"]): len(f["not_interrupted"]) for f in sw.get("functions", [])}
    print(f"rebuilt {'bundle.json' if per_lib else 'fw.elf'} matches (sha256 {got[:12]}); {len(funcs)} functions, {hit} of {tot} instructions "
          f"outside masked sections interrupted, {full} functions completely")
    key = lambda f: (f.get("library"), f["function"])
    changed = [(f["function"], old.get(key(f)), len(f["not_interrupted"])) for f in funcs
               if old.get(key(f)) != len(f["not_interrupted"])]
    for name, o, n in changed[:20]:
        print(f"  {name[:60]:60} not interrupted: {o if o is not None else '-'} -> {n}")
    if a.out:
        rec["sweep"]["functions"] = funcs
        rec["sweep"]["coverage_recomputed"] = {"by": "recompute_coverage.py", "fw_sha256_checked": True}
        with open(a.out, "w") as fh:
            json.dump(rec, fh, indent=2)
        print(f"written: {a.out}")


if __name__ == "__main__":
    main()
