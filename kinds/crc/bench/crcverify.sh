#!/usr/bin/env bash
# Rebuild the images of CRC records and compare them with the checksums in
# the records: does a number come from the code its record names? No board
# is needed and none is touched. As firmware/nrf5340-rb-bench/oneverify.sh
# (version 2), for this kind's records.
#
# Usage: bash crcverify.sh RECORD.json [RECORD.json ...]
#   records of crcrecords.py (records/crc/<board>/<adapter>.json)
#
# How: the records are taken board by board and commit by commit. The
# sources of the commit (bench_commit) are copied into a fresh directory:
# from git (git archive) when the repository has the commit, or from a tree
# without history (the public export) whose EXPORTED_FROM names it or whose
# SAME_SOURCES_CRC lists it (public-export.py: a commit with the same test
# sources of the CRC kind as the exported one). Its bench/onebuild.sh builds
# every image of the board from its slots.txt, in the toolchain image the
# records name, with the libraries at the pins of its libs.lock (fetched
# into the fresh directory, or copied from VL_LIBS_FROM and checked out
# again; a library with changed files is refused). Per record, each of its
# eight images is compared:
#   - the bytes in flash (image_sha256) decide;
#   - the address of the image, the fixed part, the boot stub, the toolchain
#     and the layout of the image must be the same too;
#   - the ELF file (fw_sha256) is reported if it differs: its debug
#     information can change without a changed byte in flash.
# Environment:
#   VL_REPO       repository or exported tree to take the sources from
#                 (default: the one this script is in)
#   VL_LIBS_FROM  a directory of the libraries (as ~/vl-next/kind-crc) to
#                 copy before fetching, to save the downloads
#   VL_TREE=1     build from the tree at hand (what is committed at HEAD)
#                 instead of from the records' commit: does this tree still
#                 build the images the records were measured from?
#   VL_KEEP=1     keep the build directories (they are printed)
# Exit: 0 every record matched, 1 one did not, 2 one could not be checked.
set -uo pipefail
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${VL_REPO:-$(cd "$HERE/../../.." && pwd)}
[ $# -ge 1 ] || { sed -n '2,34p' "$0"; exit 2; }
command -v jq >/dev/null && command -v podman >/dev/null && command -v git >/dev/null || { echo "needs jq, git and podman" >&2; exit 2; }
TMPROOT=${TMPDIR:-/tmp}
worst=0
note() { [ "$1" -gt "$worst" ] && worst=$1; return 0; }
board_dir() { case $1 in 1) echo nrf5340 ;; 2) echo stm32g0b1 ;; 3) echo stm32g474 ;; 4) echo stm32h723 ;; 5) echo samd20 ;; 6) echo rp2350 ;; esac; }

# group: "commit board image" -> records
declare -A group
for rec in "$@"; do
    base=$(basename "$(dirname "$rec")")/$(basename "$rec" .json)
    [ "$(jq -r '.schema // empty' "$rec" 2>/dev/null)" = crc-bench/1 ] || { echo "$base: not a record of the CRC kind (crc-bench/1)"; note 2; continue; }
    commit=$(jq -r '.bench_commit // empty' "$rec"); img=$(jq -r '.toolchain_image // empty' "$rec")
    board=$(board_dir "$(jq -r '.board_id' "$rec")")
    case "$commit" in ""|unknown|*+dirty) echo "$base: commit '$commit' cannot be rebuilt (unknown, or uncommitted changes)"; note 2; continue ;; esac
    [ -n "$board" ] && [ -n "$img" ] || { echo "$base: no board or toolchain image"; note 2; continue; }
    group["$commit $board $img"]+="$rec"$'\n'
done

for key in $(printf '%s\n' "${!group[@]}" | sort | tr ' ' '|'); do
    IFS='|' read -r commit board img <<<"$key"
    recs=${group["$commit $board $img"]}
    fail() { while read -r r; do [ -z "$r" ] || echo "$(basename "$(dirname "$r")")/$(basename "$r" .json): $1"; done <<<"$recs"; note 2; }
    podman image exists "$img" || { fail "toolchain image $img not present (see toolchain/README.md)"; continue; }
    tree=$(mktemp -d "$TMPROOT/vl-crcverify.XXXXXX")
    src=$commit
    if [ "${VL_TREE:-0}" = 1 ]; then
        if [ "$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)" = "$REPO" ]; then
            git -C "$REPO" archive HEAD | tar -x -C "$tree"
            src="this tree at $(git -C "$REPO" rev-parse --short=12 HEAD), records made at $commit"
        else
            cp -a "$REPO/." "$tree/"; src="this tree, records made at $commit"
        fi
    elif git -C "$REPO" cat-file -e "$commit^{commit}" 2>/dev/null; then
        git -C "$REPO" archive "$commit" | tar -x -C "$tree"
    elif { [ -f "$REPO/EXPORTED_FROM" ] && [ "$(cut -c1-12 "$REPO/EXPORTED_FROM")" = "${commit:0:12}" ]; } \
         || { [ -f "$REPO/SAME_SOURCES_CRC" ] && grep -qx "${commit:0:12}" "$REPO/SAME_SOURCES_CRC"; }; then
        cp -a "$REPO/." "$tree/"
    else
        fail "commit $commit is not in $REPO"; rm -rf "${tree:?}"; continue
    fi
    kind=$tree/kinds/crc
    [ -f "$kind/bench/onebuild.sh" ] || { fail "the sources of $src have no kinds/crc/bench/onebuild.sh"; rm -rf "${tree:?}"; continue; }
    # the toolchain image is the one onebuild.sh names; a record of another image cannot be rebuilt by it
    grep -qx "IMG=$img" "$kind/bench/onebuild.sh" || { fail "onebuild.sh of $src builds in another image than $img"; rm -rf "${tree:?}"; continue; }
    libs=$tree/libs
    if [ -n "${VL_LIBS_FROM:-}" ] && [ -d "$VL_LIBS_FROM" ]; then cp -a "$VL_LIBS_FROM" "$libs"; fi
    # fetch.sh checks out every pinned commit; a copied library with changed files is refused here
    dirty=""
    if LIBS=$libs bash "$kind/fetch.sh" > "$tree/libs.txt" 2>&1; then
        for d in "$libs"/*/; do
            [ -z "$(git -C "$d" status --porcelain 2>/dev/null)" ] || dirty="$dirty $(basename "$d")"
        done
    else
        fail "the libraries could not be fetched: $(tail -n 2 "$tree/libs.txt" | tr '\n' ' ')"; rm -rf "${tree:?}"; continue
    fi
    [ -z "$dirty" ] || { fail "libraries with changed files:$dirty"; rm -rf "${tree:?}"; continue; }
    if ! (cd "$kind/bench" && LIBS=$libs bash onebuild.sh table "$board") > "$tree/build.log" 2>&1; then
        fail "build failed ($src): $(tail -n 2 "$tree/build.log" | tr '\n' ' ')"; VL_KEEP=1; echo "  kept: $tree"; continue
    fi
    while read -r rec; do
        [ -n "$rec" ] || continue
        python3 -I - "$rec" "$kind/build/v2/$board" "$src, $img" <<'EOF'
import glob, json, os, sys
rec, built, src = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
base = os.path.basename(os.path.dirname(sys.argv[1])) + "/" + os.path.basename(sys.argv[1])[:-5]
new, man = {}, {}
for f in glob.glob(os.path.join(built, "bundle*.json")):
    m = json.load(open(f))
    for im in m["images"]:
        if im["adapter"] == rec["adapter"]:
            new[im["place"]], man = im, m
bad, elf = [], []
if rec["toolchain"] != json.load(open(os.path.join(built, "build.json")))["toolchain"]:
    bad.append("the toolchain image is not the record's (toolchain.json)")
for im in rec["images"]:
    n = new.get(im["place"])
    if n is None:
        bad.append(f"placement {im['place']}: not built")
    elif int(n["base"], 16) != int(im["image_base"], 16):
        bad.append(f"placement {im['place']}: at {n['base']}, record {im['image_base']}")
    elif n["image_sha256"] != im["image_sha256"]:
        bad.append(f"placement {im['place']}: flash bytes differ (record {im['image_sha256'][:16]}, rebuilt {n['image_sha256'][:16]})")
    elif n["sha256"] != im["fw_sha256"]:
        elf.append(im["place"])
if len(new) != len(rec["images"]):
    bad.append(f"{len(new)} placements built, {len(rec['images'])} in the record")
if man and man["fixed_sha256"] != rec["fixed_sha256"]:
    bad.append("the fixed part differs")
if man and man["boot_image_sha256"] != rec["boot_image_sha256"]:
    bad.append("the boot stub differs")
if man and man.get("layout") != rec.get("layout"):
    bad.append(f"the layout differs (record {rec.get('layout')!r}, rebuilt {man.get('layout')!r})")
note = f"; ELF file differs at placements {elf} (flash bytes the same)" if elf else ""
if bad:
    print(f"{base}: DIFFERS  ({src})\n" + "\n".join("  " + b for b in bad))
    sys.exit(3)   # 3: differs; any other exit but 0 (an error of this program) is "could not be checked"
print(f"{base}: MATCH  {len(rec['images'])} images  ({src}){note}")
EOF
        case $? in 0) ;; 3) note 1 ;; *) echo "$(basename "$(dirname "$rec")")/$(basename "$rec" .json): could not be compared (error above)"; note 2 ;; esac
    done <<<"$recs"
    if [ "${VL_KEEP:-0}" = 1 ]; then echo "  kept: $tree"; else rm -rf "${tree:?}"; fi
done
exit "$worst"
