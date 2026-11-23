#!/bin/bash
# Rebuild the firmware of a result record and compare it with the record's
# fw_sha256: does the published number come from the code the record names?
# No board is needed and none is touched.
#
# Usage: lab/tools/verify-build.sh RECORD.json [RECORD.json ...]
#   Records of the benchmark (*-rb-bench-*), the ISR stress test
#   (*-rb-stress-*) and the two-interrupt stress test (*-rb-mp-stress-*).
#   Records of benchmark version 2 (records/bench-v2/<board>/<adapter>.json,
#   one image per configuration) are handed to
#   firmware/nrf5340-rb-bench/oneverify.sh, which says how they are compared.
#
# How: the source of the record's commit (source_commit / bench_commit) is
# copied into a fresh directory, from git (git archive) when the repository
# has that commit, or from a tree without history (the public export) whose
# EXPORTED_FROM file names it or whose SAME_SOURCES file lists it (a commit
# with the same firmware/ as the exported one: the records are committed
# after the commit they were made at). That commit's own run.sh then builds the
# firmware with the record's settings (board, set, mode, code location,
# optimisation, compiler, memcpy, extra -D flags), in the toolchain image the
# record names. run.sh stops at the first board access: PATH starts with a
# probe-rs (and openocd) that only exits with an error, so the build steps
# are exactly the ones the lab ran and the board steps never run.
# The image must be present locally under the record's name
# (toolchain/README.md has the recipes); its /etc/verified-libs/toolchain.json
# is compared with the record's "toolchain" too.
#
# Environment:
#   VL_REPO       repository or exported tree to take the source from
#                 (default: the one this script is in)
#   VL_LIBS_FROM  a firmware/nrf5340-rb-bench/build/libs directory to copy
#                 the library clones from before fetching (saves the
#                 downloads; fetch-libs.sh still checks out and verifies
#                 every pinned commit)
#   VL_COMMIT     the commit for records that do not name one (records
#                 before 2026-11-12 20:16 CET: the campaign's commit); used
#                 only when the record has no commit field, and reported
#   VL_TREE=1     build from the tree at hand (REPO: what is committed at
#                 HEAD, or an exported tree as it is) instead of from the
#                 record's commit: does this tree still build the image
#                 the record was measured from (DECISIONS 2026-11-22)? For
#                 a stress record that differs, the libraries whose images
#                 differ are named; the others still match.
#   VL_KEEP=1     keep the build directory (it is printed)
# Exit: 0 if every record matched, 1 if one did not, 2 if one could not be
# checked (dirty or unknown commit, commit not available, missing image,
# build failed).
set -uo pipefail
export LC_ALL=C
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${VL_REPO:-$(cd "$HERE/../.." && pwd)}
[ $# -ge 1 ] || { sed -n '2,30p' "$0"; exit 2; }
command -v jq >/dev/null && command -v podman >/dev/null || { echo "needs jq and podman" >&2; exit 2; }

TMPROOT=${TMPDIR:-/tmp}
STUB=$(mktemp -d "$TMPROOT/vl-verify-stub.XXXXXX")
for t in probe-rs openocd; do
    printf '#!/bin/sh\necho "verify-build: no board access (%s)" >&2\nexit 97\n' "$t" > "$STUB/$t"
    chmod +x "$STUB/$t"
done
trap 'rm -rf "${STUB:?}"' EXIT

worst=0
note() { [ "$1" -gt "$worst" ] && worst=$1; }

verify_one() {
    local rec=$1 base kind board mode commit img tree fwdir elf want got code
    base=$(basename "$rec" .json)
    case "$base" in
        *-rb-mp-stress-*) kind=mp ;;
        *-rb-stress-*)    kind=stress ;;
        *-rb-bench-*)     kind=bench ;;
        *) echo "$base: not a benchmark or stress record"; return 2 ;;
    esac
    board=${base%%-rb-*}
    want=$(jq -r '.fw_sha256 // empty' "$rec")
    commit=$(jq -r '.source_commit // .bench_commit // empty' "$rec")
    local given=""
    if [ -z "$commit" ] && [ -n "${VL_COMMIT:-}" ]; then commit=$VL_COMMIT; given=" (commit given by VL_COMMIT, not in the record)"; fi
    img=$(jq -r '.toolchain_image // empty' "$rec")
    [ -n "$want" ] || { echo "$base: no fw_sha256"; return 2; }
    case "$commit" in
        "") echo "$base: the record names no commit (older record: set VL_COMMIT from its campaign)"; return 2 ;;
        unknown|*+dirty) echo "$base: commit '$commit' cannot be rebuilt (unknown, or uncommitted changes)"; return 2 ;; esac
    podman image exists "$img" || { echo "$base: toolchain image $img not present (see toolchain/README.md)"; return 2; }

    tree=$(mktemp -d "$TMPROOT/vl-verify.XXXXXX")
    local src="$commit"
    if [ "${VL_TREE:-0}" = 1 ]; then
        # The tree at hand, whatever commit the record names: what is
        # committed at HEAD if REPO is a git repository, else REPO as it is.
        if [ "$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)" = "$REPO" ]; then
            git -C "$REPO" archive HEAD | tar -x -C "$tree"
            src="this tree at $(git -C "$REPO" rev-parse --short=12 HEAD), record made at $commit"
        else
            cp -a "$REPO/." "$tree/"
            src="this tree, record made at $commit"
        fi
    elif git -C "$REPO" cat-file -e "$commit^{commit}" 2>/dev/null; then
        git -C "$REPO" archive "$commit" | tar -x -C "$tree"
    elif { [ -f "$REPO/EXPORTED_FROM" ] && [ "$(cut -c1-12 "$REPO/EXPORTED_FROM")" = "${commit:0:12}" ]; } \
         || { [ -f "$REPO/SAME_SOURCES" ] && grep -qx "${commit:0:12}" "$REPO/SAME_SOURCES"; }; then
        cp -a "$REPO/." "$tree/"
    elif pub=$(jq -r --arg c "${commit:0:12}" '.series[] | select(.commit[0:12] == $c) | .public_commit' "$REPO/records/archived.json" 2>/dev/null) \
         && [ -n "$pub" ]; then
        # an archived series: its sources are those of the public commit it was published as
        if git -C "$REPO" cat-file -e "$pub^{commit}" 2>/dev/null; then
            git -C "$REPO" archive "$pub" | tar -x -C "$tree"
            src="$commit, archived series, public commit ${pub:0:12}"
        else
            echo "$base: commit $commit is of an archived series (records/archived.json): this needs the history of the public repository, where it is commit ${pub:0:12}"
            rm -rf "${tree:?}"; return 2
        fi
    else
        echo "$base: commit $commit is not in $REPO"; rm -rf "${tree:?}"; return 2
    fi
    if [ -n "${VL_LIBS_FROM:-}" ] && [ -d "$VL_LIBS_FROM" ]; then
        mkdir -p "$tree/firmware/nrf5340-rb-bench/build"
        cp -a "$VL_LIBS_FROM" "$tree/firmware/nrf5340-rb-bench/build/libs"
    fi

    # The record's settings as run.sh's environment and argument.
    local opt lto comp memcpy set loc flags env arg
    opt=$(jq -r '.opt // "-O2"' "$rec")
    lto=$(jq -r 'if .lto == true then 1 else 0 end' "$rec")
    comp=$(jq -r '.compiler_libs // "gcc"' "$rec"); comp=${comp%% *}; [ "$comp" = arm-none-eabi-gcc ] && comp=gcc
    loc=$(jq -r '.code_location // "flash"' "$rec")
    flags=$(jq -r '.build_flags // ""' "$rec")
    case $kind in
        bench)
            set=$(jq -r '.set // "spsc"' "$rec")
            case "$(jq -r '.memcpy // ""' "$rec")" in
                "newlib memcpy-stub"*) memcpy=stub ;; "Rust compiler_builtins"*) memcpy=rust ;; *) memcpy=newlib ;; esac
            env=(SET="$set" MEMCPY="$memcpy" SHIFT="$(jq -r '.shift // 0' "$rec")"); arg=$loc
            fwdir=firmware/nrf5340-rb-bench; elf=build/$loc/fw.elf ;;
        stress)
            mode=${base#*-rb-stress-}; mode=${mode%-*}
            # build_flags is the mode's -D flags followed by STRESS_PARAMS
            local sp="" tok
            for tok in $flags; do
                case "$tok" in -DBLOCK_MODE=1|-DDMA_MODE=1|-DSMP_MODE=1|-DSWEEP_MODE=1|-DSWEEP_MODE=2) ;; *) sp="$sp $tok" ;; esac
            done
            # params_at_runtime (since 2026-11-15): one image for every mode,
            # build_flags holds only what was compiled in
            # images.kind per_library (since 2026-11-15): one image per
            # library, fw_sha256 is that of build/bundle.json (it lists every
            # image's sha256; a mismatch names the libraries below)
            local ims=one; elf=build/fw.elf
            # images.kind combined (since 2026-11-17): the same images in one
            # bundle with the MP test's (run.sh IMAGES=combined)
            case "$(jq -r '.images.kind // ""' "$rec")" in
                per_library) ims=per_lib; elf=build/bundle.json ;;
                combined) ims=combined; elf=build/bundle.json ;; esac
            env=(CODE="$loc" STRESS_PARAMS="${sp# }" IMAGES="$ims"
                 PARAMS_AT_RUNTIME="$(jq -r 'if .params_at_runtime == true then 1 else 0 end' "$rec")"); arg=$mode
            fwdir=firmware/nrf5340-rb-stress ;;
        mp)
            mode=${base#*-rb-mp-stress-}; mode=${mode%-*}
            # the name goes on after the mode: -extra, -lib<n>, -perlib,
            # -combined, and since 2026-11-17 -cov, -aim<a>w<n>, -norec
            mode=$(echo "$mode" | sed -E 's/^((smp-)?(mpsc|spmc)).*$/\1/')
            env=(CODE="$loc" MP_PARAMS="$flags" WITH_EXTRA="$(jq -r 'if .with_extra == true then 1 else 0 end' "$rec")"); arg=$mode
            fwdir=firmware/rb-mp-stress; elf=build/fw.elf
            local only mpims
            only=$(jq -r '.only_lib // empty' "$rec")
            [ -z "$only" ] || { env+=(ONLY="$only"); elf=build/lib$only/fw.elf; }
            # per_lib (since 2026-11-17): one library per reset over the
            # serial port; UART_TTY only so run.sh gets past its check (the
            # build is done before the serial port is opened)
            mpims=$(jq -r '.per_lib.images // empty' "$rec")
            if [ -n "$mpims" ]; then
                env+=(PER_LIB=1 IMAGES="$mpims" UART_TTY=/dev/null)
                case "$mpims" in per_lib) elf=build/bundle.json ;; combined) elf=../nrf5340-rb-stress/build/bundle.json ;; esac
            fi ;;
    esac

    # run.sh builds, then fails at its first probe-rs call (exit 97 from the stub).
    ( cd "$tree/$fwdir" && PATH="$STUB:$PATH" BOARD="$board" OPT="$opt" LTO="$lto" COMPILER="$comp" \
        OUTDIR="$tree/out" env "${env[@]}" bash run.sh "$arg" ) > "$tree/verify.log" 2>&1
    code=$?
    if [ ! -f "$tree/$fwdir/$elf" ]; then
        echo "$base: build failed (run.sh exit $code), log: $tree/verify.log"
        return 2
    fi
    got=$(sha256sum "$tree/$fwdir/$elf" | cut -d' ' -f1)
    local tc_rec tc_img tcnote=""
    tc_rec=$(jq -cS '.toolchain // empty' "$rec")
    tc_img=$(podman run --rm "$img" cat /etc/verified-libs/toolchain.json 2>/dev/null | jq -cS . 2>/dev/null)
    [ -z "$tc_rec" ] || [ "$tc_rec" = "$tc_img" ] || tcnote=" (image $img reports other tool versions than the record)"
    local r=0 keep=${VL_KEEP:-0}
    if [ "$got" = "$want" ]; then
        echo "$base: MATCH  $got  ($src, $img)$tcnote$given"
    else
        echo "$base: DIFFERS  record $want, rebuilt $got  ($src, $img)$tcnote$given"; r=1; keep=1
        if [ "$elf" = build/bundle.json ]; then
            # per library: which images differ (the others still match)
            jq -r --slurpfile b "$tree/$fwdir/$elf" '.images.libs | to_entries[]
                | select(.value.sha256 != ($b[0].libs[.key].sha256 // "")) | "  library \(.key): image differs"' "$rec"
        fi
    fi
    if [ "$keep" = 1 ]; then echo "  build kept in $tree"; else rm -rf "${tree:?}"; fi
    return $r
}

# records of benchmark version 2 (one image per configuration) are rebuilt
# board by board, by the tool beside their build: oneverify.sh
two=()
for rec in "$@"; do
    if [ "$(jq -r '.schema // empty' "$rec" 2>/dev/null)" = rb-bench/2 ]; then two+=("$rec"); continue; fi
    verify_one "$rec"; note $?
done
if [ ${#two[@]} -gt 0 ]; then
    VL_REPO=$REPO bash "$HERE/../../firmware/nrf5340-rb-bench/oneverify.sh" "${two[@]}"; note $?
fi
exit $worst
