#!/bin/sh
# Take the objects that define memcpy, memmove, memset and memcmp from a C
# library archive, so a firmware can link them in place of newlib-nano's
# (bench LIBC=; common/libc.mk). Runs inside the toolchain image.
# Usage: libc-objs.sh ARCHIVE OUTDIR NM AR
# Prints the extracted object paths; fails if a symbol is not defined in
# the archive, or if the objects need other symbols of that library.
set -eu
a=$1 out=$2 nm=$3 ar=$4
rm -rf "${out:?}"; mkdir -p "$out"
mem=""
for s in memcpy memmove memset memcmp; do
    m=$($nm -A --defined-only "$a" 2>/dev/null | awk -v s="$s" '$NF == s && ($(NF-1) == "T" || $(NF-1) == "W") {print $1; exit}' \
        | sed 's/:[0-9a-fA-F]*$//; s/:$//; s/^.*://')   # GNU nm: ARCHIVE:MEMBER:ADDR, llvm-nm: ARCHIVE:MEMBER:
    [ -n "$m" ] || { echo "libc-objs.sh: $s not defined in $a" >&2; exit 1; }
    case " $mem " in *" $m "*) ;; *) mem="$mem $m" ;; esac
done
# shellcheck disable=SC2086
(cd "$out" && $ar x "$a" $mem)
for m in $mem; do echo "$out/$m"; done
