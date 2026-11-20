#!/bin/bash
# What each configuration adds to a firmware, in flash and in RAM. No board.
# Usage: BOARD=stm32g474 bash size.sh
# Environment: BOARD as run.sh (default nrf5340); OPT (default -O2);
#   COMPILER gcc (default) or clang; OUTDIR (default ~/lab-runs).
# Writes OUTDIR/<board>-rb-size[-flags]-<time>.json and prints a table.
#
# (../rb-size measures something else: several buffers of one library in one
# firmware, for a hand-kept list of libraries.)
#
# How: for every configuration of the three benchmark sets (spsc, rust, mp)
# the benchmark firmware is linked with that one entry in its table
# (Makefile, build/size/<adapter>.elf) and compared with the same firmware
# with no library (adapter_none). The linker's --gc-sections keeps what the
# configuration needs: the library's code, our adapter (a few small functions
# per configuration), the buffer and whatever else it pulls in (division or
# atomic helpers on Cortex-M0+, our FreeRTOS shim, critical-section code).
#   flash = text + initialised data,  RAM = data + bss  (arm-none-eabi-size)
# - The benchmark's 32-byte alignment of the adapters' and the Rust functions
#   is off in these builds (make SIZE=1), so no padding is counted and each
#   configuration of a source file with several is linked alone.
# - Buffers hold 127 or 128 bytes, so RAM includes about 128 bytes of storage.
# - memcpy, memmove and memset of the C library are in every firmware here,
#   also the empty one, so they are not counted.
# - A configuration that allocates at start-up ("heap": true) links our bump
#   allocator; its arena (BENCH_HEAP_SIZE) is taken out of the RAM number, so
#   that number lacks what the library allocates.
# - A configuration that does not exist on the core (no compare-and-swap on
#   Cortex-M0+) has an empty adapter there: "available": false.
set -euo pipefail
cd "$(dirname "$0")"
export LC_ALL=C
BOARD=${BOARD:-nrf5340}
[ -d "../common/$BOARD" ] || { echo "unknown BOARD $BOARD" >&2; exit 2; }
OPT=${OPT:--O2}
case "$OPT" in -O0|-O1|-O2|-O3|-Os|-Og|-Oz) ;; *) echo "OPT must be one of -O0..-O3, -Os, -Og, -Oz" >&2; exit 2 ;; esac
COMPILER=${COMPILER:-gcc}
case "$COMPILER" in gcc|clang) ;; *) echo "COMPILER must be gcc or clang" >&2; exit 2 ;; esac
IMG=verified-libs/toolchain:2026-11-13   # the sets with Rust code need it; its C compilers are those of 2026-11-05
OUTDIR=${OUTDIR:-$HOME/lab-runs}
SUFFIX=""
[ "$OPT" = -O2 ] || SUFFIX="-${OPT#-}"
[ "$COMPILER" = gcc ] || SUFFIX="$SUFFIX-$COMPILER"

mkdir -p build "$OUTDIR"
libs=$(bash fetch-libs.sh)
work=$(mktemp -d build/sizework.XXXXXX)
trap 'rm -rf "${work:?}"' EXIT
python3 - main.c > "$work/sets.txt" <<'EOF'
import re, sys
src = open(sys.argv[1]).read()
tab = src[src.index("const rb_adapter *libs[NLIBS] = {"):]
tab = tab[:tab.index("#endif")]
# the table's branches by their condition (the nordic set is not sized:
# its sources come from the nRF5 SDK and may be built for Nordic chips only)
names = {"BENCH_MP": "mp", "BENCH_RUST": "rust", "": "spsc"}
parts = re.split(r"^#(?:ifdef|elif|else)\b(.*)$", tab, flags=re.M)   # [head, cond, text, cond, text, ...]
for cond, text in zip(parts[1::2], parts[2::2]):
    m = re.search(r"BENCH_\w+", cond)
    name = names.get(m.group(0) if m else "")
    if name:
        print(name, " ".join(re.findall(r"&(adapter_\w+)", text)))
EOF
while read -r set syms; do
    targets=""
    for s in adapter_none $syms; do [ "$s" = adapter_baseline ] || targets="$targets build/size/$s.elf"; done
    podman run --rm -v "$PWD/..":/work:Z -w /work/nrf5340-rb-bench "$IMG" \
        sh -c "make clean >/dev/null; make BOARD=$BOARD SET=$set OPT='$OPT' COMPILER=$COMPILER SIZE=1 $targets >build/make-size-$set.log 2>&1 \
               && arm-none-eabi-size $targets && for e in $targets; do echo \"nm \$e\"; arm-none-eabi-nm -S \$e | grep -E ' (malloc|arena|[A-Za-z_0-9]*_reset)\$' || true; done" \
        > "$work/$set.txt" || { echo "build failed, see build/make-size-$set.log" >&2; exit 1; }
done < "$work/sets.txt"
toolchain=$(podman run --rm "$IMG" cat /etc/verified-libs/toolchain.json)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$OUTDIR/$BOARD-rb-size$SUFFIX-$stamp.json"
python3 - "$work" "$out" <<EOF
import json, os, re, sys
sys.path.insert(0, ".")
from decode import LIBS, LIBS_MP, LIBS_RUST
work, out = sys.argv[1], sys.argv[2]
names = {"spsc": LIBS, "mp": LIBS_MP, "rust": LIBS_RUST}
rec = {"board": "$BOARD", "time": "$stamp", "opt": "$OPT", "compiler_libs": "$COMPILER",
       "source_commit": """$(bash ../../lab/tools/source-commit.sh .)""".strip(),
       "toolchain_image": "$IMG", "toolchain": json.loads('''$toolchain'''),
       "libraries": """$libs""".split("\n"), "sets": {}, "libs": []}
seen = set()
for line in open(os.path.join(work, "sets.txt")):
    st, *syms = line.split()
    assert len(syms) == len(names[st]), (st, len(syms), len(names[st]))
    size, extra, cur = {}, {}, None
    for l in open(os.path.join(work, st + ".txt")):
        f = l.split()
        if len(f) == 6 and f[0].isdigit():                      # text data bss dec hex filename
            size[os.path.basename(f[5])[:-4]] = tuple(int(x) for x in f[:3])
        elif f and f[0] == "nm":
            cur = os.path.basename(f[1])[:-4]; extra[cur] = {}
        elif len(f) == 4:
            extra[cur][f[3]] = int(f[1], 16)
    t0, d0, b0 = size["adapter_none"]
    rec["sets"][st] = {"none": {"text": t0, "data": d0, "bss": b0}}
    for sym, name in zip(syms, names[st]):
        if sym == "adapter_baseline" or name in seen:
            continue
        seen.add(name)
        t, d, b = size[sym]
        arena = extra[sym].get("arena", 0)
        e = {"name": name, "set": st, "adapter": sym, "flash": t + d - t0 - d0, "ram": d + b - d0 - b0 - arena,
             "text": t - t0, "data": d - d0, "bss": b - b0, "heap": "malloc" in extra[sym],
             "available": t + d - t0 - d0 > 16}
        rec["libs"].append(e)
json.dump(rec, open(out, "w"), indent=1)
print(f"{'configuration':50} {'flash':>6} {'RAM':>6}")
for e in rec["libs"]:
    print(f"{e['name'][:50]:50} {e['flash']:6} {e['ram']:6}{' + heap' if e['heap'] else ''}{'' if e['available'] else '  (not on this core)'}")
print("record:", out)
EOF
