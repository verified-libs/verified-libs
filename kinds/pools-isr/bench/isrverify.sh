#!/usr/bin/env bash
# Rebuild the images of pools concurrency records and compare them with the
# checksums in the records: does a verdict come from the code its record
# names? No board is needed and none is touched. As
# kinds/pools/bench/poolverify.sh (the pools kind), for this series' records.
#
# Usage: bash isrverify.sh RECORD.json [RECORD.json ...]
#   records of isrrecords.py (records/pools-isr/<board>/<adapter>.json, pools-isr/1)
#
# How: the records are taken board by board and commit by commit. The
# sources of the commit (bench_commit) are copied into a fresh directory:
# from git (git archive) when the repository has the commit, or from a tree
# without history (the public export) whose EXPORTED_FROM names it or whose
# SAME_SOURCES_POOLS_ISR lists it (public-export.py: a commit with the same
# test sources of the pools concurrency kind as the exported one). Its
# kinds/pools-isr/onebuild.sh builds every image of the board and the
# bundle the record names (BUNDLE: 300 into build/v1, 301 into build/b301;
# a commit before bundle 301 builds bundle 300 only), in the toolchain image the records name, with the libraries at
# the pins of kinds/pools/libs.lock (fetched into the fresh directory, or
# copied from VL_LIBS_FROM and checked out again; a library with changed
# files is refused). Per record, its one image is compared:
#   - the bytes in flash (image_sha256) decide;
#   - the address of the image, the boot stub, the bundle (its number and
#     checksum: every image of the board, as it was on the board), the
#     toolchain and the libraries' pins must be the record's too;
#   - the ELF file (fw_sha256) is reported if it differs: its debug
#     information can change without a changed byte in flash.
# Environment:
#   VL_REPO       repository or exported tree to take the sources from
#                 (default: the one this script is in)
#   VL_LIBS_FROM  a directory of the libraries (as ~/vl-next/kind-pools) to
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
[ $# -ge 1 ] || { sed -n '2,37p' "$0"; exit 2; }
command -v jq >/dev/null && command -v podman >/dev/null && command -v git >/dev/null || { echo "needs jq, git and podman" >&2; exit 2; }
TMPROOT=${TMPDIR:-/tmp}
worst=0
note() { [ "$1" -gt "$worst" ] && worst=$1; return 0; }
BOARDS=" nrf5340 stm32g0b1 stm32g474 stm32h723 samd20 rp2350 "

# group: "commit board image" -> records
declare -A group
for rec in "$@"; do
    base=$(basename "$(dirname "$rec")")/$(basename "$rec" .json)
    case "$(jq -r '.schema // empty' "$rec" 2>/dev/null)" in pools-isr/1) true ;; *) false ;; esac || { echo "$base: not a record of the pools concurrency series (pools-isr/1)"; note 2; continue; }
    commit=$(jq -r '.bench_commit // empty' "$rec"); img=$(jq -r '.toolchain_image // empty' "$rec")
    board=$(jq -r '.board // empty' "$rec"); bundle=$(jq -r '.bundle // empty' "$rec")
    case "$commit" in ""|unknown|*+dirty) echo "$base: commit '$commit' cannot be rebuilt (unknown, or uncommitted changes)"; note 2; continue ;; esac
    case "$BOARDS" in *" $board "*) ;; *) echo "$base: no board of the series ('$board')"; note 2; continue ;; esac
    [ -n "$img" ] || { echo "$base: no toolchain image"; note 2; continue; }
    case "$bundle" in 300|301) ;; *) echo "$base: no bundle of the series ('$bundle')"; note 2; continue ;; esac
    group["$commit $board $img $bundle"]+="$rec"$'\n'
done

for key in $(printf '%s\n' "${!group[@]}" | sort | tr ' ' '|'); do
    IFS='|' read -r commit board img bundle <<<"$key"
    recs=${group["$commit $board $img $bundle"]}
    case "$bundle" in 300) out=v1 ;; *) out=b$bundle ;; esac
    fail() { while read -r r; do [ -z "$r" ] || echo "$(basename "$(dirname "$r")")/$(basename "$r" .json): $1"; done <<<"$recs"; note 2; }
    podman image exists "$img" || { fail "toolchain image $img not present (see toolchain/README.md)"; continue; }
    tree=$(mktemp -d "$TMPROOT/vl-isrverify.XXXXXX")
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
         || { [ -f "$REPO/SAME_SOURCES_POOLS_ISR" ] && grep -qx "${commit:0:12}" "$REPO/SAME_SOURCES_POOLS_ISR"; }; then
        cp -a "$REPO/." "$tree/"
    else
        fail "commit $commit is not in $REPO"; rm -rf "${tree:?}"; continue
    fi
    kind=$tree/kinds/pools-isr
    [ -f "$kind/onebuild.sh" ] && [ -f "$tree/kinds/pools/fetch.sh" ] || { fail "the sources of $src have no kinds/pools-isr/onebuild.sh or kinds/pools/fetch.sh"; rm -rf "${tree:?}"; continue; }
    # the toolchain image is the one onebuild.sh names; a record of another image cannot be rebuilt by it
    grep -qx "IMG=$img" "$kind/onebuild.sh" || { fail "onebuild.sh of $src builds in another image than $img"; rm -rf "${tree:?}"; continue; }
    rm -rf "${kind:?}/build"   # a tree without history may carry a build: never compare with that, only with this one
    libs=$tree/libs
    if [ -n "${VL_LIBS_FROM:-}" ] && [ -d "$VL_LIBS_FROM" ]; then cp -a "$VL_LIBS_FROM" "$libs"; fi
    # fetch.sh checks out every pinned commit; a copied library with changed files is refused here
    dirty=""
    if LIBS=$libs bash "$tree/kinds/pools/fetch.sh" > "$tree/libs.txt" 2>&1; then
        for d in "$libs"/*/; do
            [ -z "$(git -C "$d" status --porcelain 2>/dev/null)" ] || dirty="$dirty $(basename "$d")"
        done
    else
        fail "the libraries could not be fetched: $(tail -n 2 "$tree/libs.txt" | tr '\n' ' ')"; rm -rf "${tree:?}"; continue
    fi
    [ -z "$dirty" ] || { fail "libraries with changed files:$dirty"; rm -rf "${tree:?}"; continue; }
    if ! (cd "$kind" && LIBS=$libs BUNDLE=$bundle bash onebuild.sh "$board") > "$tree/build.log" 2>&1; then
        fail "build failed ($src): $(tail -n 2 "$tree/build.log" | tr '\n' ' ')"; VL_KEEP=1; echo "  kept: $tree"; continue
    fi
    while read -r rec; do
        [ -n "$rec" ] || continue
        python3 -I - "$rec" "$kind/build/$out/$board" "$src, $img" <<'EOF'
import glob, json, os, sys
rec, built, src = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
base = os.path.basename(os.path.dirname(sys.argv[1])) + "/" + os.path.basename(sys.argv[1])[:-5]
mans = glob.glob(os.path.join(built, "bundle*.json"))
bj = json.load(open(os.path.join(built, "build.json")))
bad, note = [], ""
if len(mans) != 1:
    bad.append(f"{len(mans)} bundle manifests built, not one")
else:
    man = json.load(open(mans[0]))
    ims = [im for im in man["images"] if im["adapter"] == rec["adapter"]]
    if len(ims) != 1:
        bad.append(f"{len(ims)} images of {rec['adapter']} built, not one")
    else:
        im = ims[0]
        if int(im["base"], 16) != int(rec["image_base"], 16):
            bad.append(f"the image is at {im['base']}, the record's at {rec['image_base']}")
        elif im["image_sha256"] != rec["image_sha256"]:
            bad.append(f"flash bytes differ (record {rec['image_sha256'][:16]}, rebuilt {im['image_sha256'][:16]})")
        elif im["sha256"] != rec.get("fw_sha256"):
            note = "; ELF file differs (flash bytes the same)"
    if man.get("bundle") != rec["bundle"] or man["bundle_sha256"] != rec["bundle_sha256"]:
        bad.append(f"the bundle differs (record {rec['bundle']} {rec['bundle_sha256'][:16]}, "
                   f"rebuilt {man.get('bundle')} {man['bundle_sha256'][:16]})")
    if man["boot_image_sha256"] != rec["boot_image_sha256"]:
        bad.append("the boot stub differs")
if bj["toolchain"] != rec["toolchain"]:
    bad.append("the toolchain image is not the record's (toolchain.json)")
if bj["libs_pinned"] != rec["libs_pinned"]:
    bad.append("the libraries' pins are not the record's")
if bad:
    print(f"{base}: DIFFERS  ({src})\n" + "\n".join("  " + b for b in bad))
    sys.exit(3)   # 3: differs; any other exit but 0 (an error of this program) is "could not be checked"
print(f"{base}: MATCH  1 image, bundle {rec['bundle']}  ({src}){note}")
EOF
        case $? in 0) ;; 3) note 1 ;; *) echo "$(basename "$(dirname "$rec")")/$(basename "$rec" .json): could not be compared (error above)"; note 2 ;; esac
    done <<<"$recs"
    if [ "${VL_KEEP:-0}" = 1 ]; then echo "  kept: $tree"; else rm -rf "${tree:?}"; fi
done
exit "$worst"
