#!/bin/bash
# The CBMC proofs of the CRC kind, inside the toolchain image (make proof).
# Every proof gets at most 60 minutes of wall time (the plan); a proof that
# does not finish is reported as such. Up to JOBS proofs (default 4) run at
# the same time, each on its own core; the lines are printed in the order
# below, one per proof, with the wall time of each.
set -uo pipefail
cd "$(dirname "$0")"
LIBS=${LIBS:-/libs}
JOBS=${JOBS:-4}
GEN=../build/gen/src
I="-I.. -I$GEN -I$LIBS/zlib -I../shims/zephyr -I$LIBS/zephyr/include"
# The sources are preprocessed by the boards' compiler (arm-none-eabi-gcc for
# the Cortex-M4, newlib's headers) and checked with CBMC's ARM data model
# (--arch arm: 32-bit int, long and pointers, little-endian), so the types
# and the library's choices made by the preprocessor are those of a board.
CB="cbmc --arch arm --unwinding-assertions"
TMP=$(mktemp -d)

verdict() {   # rc, output
    if [ "$1" -eq 124 ]; then echo "did not finish within 60 minutes"
    elif echo "$2" | grep -q "^VERIFICATION SUCCESSFUL"; then echo "proven"
    elif echo "$2" | grep -q "^VERIFICATION FAILED"; then echo "FAILED: $(echo "$2" | grep -m1 'FAILURE' | sed 's/^ *//')"
    else echo "error: $(echo "$2" | tail -n 3 | tr '\n' ' ')"; fi
}

# prove ID LABEL HARNESS DEFINE... -- LIBRARY-FILE...
# Only the harness is preprocessed with the defines; the reference and the
# library's files without them. A token UNWIND=N among the defines is not a
# define: it sets CBMC's unwind bound for this proof (34 without one).
prove() {
    local id=$1 label=$2 h=$3; shift 3
    local defs=() f k=0 d="$TMP/$id" t0=$SECONDS out rc unwind=34
    while [ "$1" != "--" ]; do
        case $1 in UNWIND=*) unwind=${1#UNWIND=} ;; *) defs+=("-D$1") ;; esac
        shift
    done; shift
    mkdir -p "$d"
    for f in "$h" ../ref_crc.c "$@"; do
        k=$((k + 1))
        if [ "$f" = "$h" ]; then set -- "${defs[@]}"; else set --; fi
        arm-none-eabi-gcc -E -mcpu=cortex-m4 -mthumb "$@" $I "$f" -o "$d/$k.i" 2>>"$d/cpp.err" ||
            { echo "$label: error preprocessing $f" >"$TMP/$id.line"; return; }
    done
    out=$(timeout 3600 $CB --unwind "$unwind" "$d"/*.i 2>&1); rc=$?
    printf '%-48s %5ss  %s\n' "$label" "$((SECONDS - t0))" "$(verdict $rc "$out")" >"$TMP/$id.line"
}

# Part 2 of the slicing proof (word_exhaustive.c): all 2^32 values, built by
# the host's compiler; the control must report exactly its one wrong value.
exhaustive() {   # ID LABEL EXTRA-CFLAGS
    local id=$1 label=$2 extra=$3 t0=$SECONDS out
    # shellcheck disable=SC2086
    gcc -O2 -Wall -Wextra -pthread $extra -I.. -I$GEN word_exhaustive.c ../ref_crc.c "$GEN/crc32iso_hdlc.c" \
        -o "$TMP/$id.bin" || { echo "$label: error building" >"$TMP/$id.line"; return; }
    out=$(timeout 3600 "$TMP/$id.bin" 2>&1)
    printf '%-48s %5ss  %s\n' "$label" "$((SECONDS - t0))" "$(echo "$out" | tail -n 1)" >"$TMP/$id.line"
}

# Part B of zlib's braided loop (braid_linear.c): braid(), crc_word() and
# the reference over four zero bytes are linear, all 2^32 values of each,
# built by the host's compiler with zlib's 4-byte words (-DZ_TESTW=4).
linear() {   # ID LABEL EXTRA-CFLAGS
    local id=$1 label=$2 extra=$3 t0=$SECONDS out
    # shellcheck disable=SC2086
    gcc -O2 -Wall -pthread -DZ_TESTW=4 $extra -I.. -I$LIBS/zlib braid_linear.c ../ref_crc.c \
        -o "$TMP/$id.bin" 2>"$TMP/$id.err" || { echo "$label: error building" >"$TMP/$id.line"; return; }
    out=$(timeout 3600 "$TMP/$id.bin" 2>&1)
    printf '%-48s %5ss  %s\n' "$label" "$((SECONDS - t0))" "$(echo "$out" | paste -sd ';' | sed 's/;/; /g')" >"$TMP/$id.line"
}

# Part F: what part B (host, -DZ_TESTW=4) computes with is what parts A and
# D (the boards' compiler) prove with: the typedefs of z_crc_t and z_word_t,
# the initialisers of crc_table and crc_braid_table, and the body of
# crc_word(), as preprocessed, are the same text.
tables() {   # ID LABEL
    local id=$1 label=$2 t0=$SECONDS a b
    gcc -E -P -DZ_TESTW=4 -I$LIBS/zlib "$LIBS/zlib/crc32.c" -o "$TMP/$id.host.i" &&
        arm-none-eabi-gcc -E -P -mcpu=cortex-m4 -mthumb $I "$LIBS/zlib/crc32.c" -o "$TMP/$id.arm.i" ||
        { echo "$label: error preprocessing" >"$TMP/$id.line"; return; }
    for f in host arm; do
        awk '/typedef .* z_(crc|word)_t;/ {print; next}
             /crc_table\[\] = \{|crc_braid_table\[\]\[256\] = \{/ {on = 1}
             /crc_word\(z_word_t data\) \{/ {fn = 1}
             on || fn {print} on && /\};/ {on = 0} fn && /^\}/ {fn = 0}' \
            "$TMP/$id.$f.i" >"$TMP/$id.$f.tab"
    done
    a=$(grep -c . "$TMP/$id.host.tab"); b=$(grep -c . "$TMP/$id.arm.tab")
    if [ "$a" -gt 0 ] && [ "$(grep -c 'crc_braid_table' "$TMP/$id.host.tab")" -eq 1 ] &&
       [ "$(grep -c 'crc_word(z_word_t data)' "$TMP/$id.host.tab")" -eq 1 ] &&
       [ "$(grep -c 'typedef .* z_\(crc\|word\)_t;' "$TMP/$id.host.tab")" -eq 2 ] && cmp -s "$TMP/$id.host.tab" "$TMP/$id.arm.tab"; then
        printf '%-48s %5ss  %s\n' "$label" "$((SECONDS - t0))" "the same text ($a lines)" >"$TMP/$id.line"
    else
        printf '%-48s %5ss  %s\n' "$label" "$((SECONDS - t0))" "DIFFERENT or missing (host $a lines, board $b)" >"$TMP/$id.line"
    fi
}

W="$GEN/crc32iso_hdlc.c"
Z="$LIBS/zlib/crc32.c"
L=(
  "a|crcany crc32iso_hdlc_byte, 1 byte|harness.c H_CRCANY_BYTE MSG_LEN=1 OFF=0 -- $W"
  "b|crcany crc32iso_hdlc_byte, 8 bytes|harness.c H_CRCANY_BYTE MSG_LEN=8 OFF=0 -- $W"
  "c|zephyr crc32_ieee_update, 1 byte|harness.c H_ZEPHYR MSG_LEN=1 OFF=0 -- $LIBS/zephyr/subsys/crc/crc32_sw.c"
  "d|zephyr crc32_ieee_update, 8 bytes|harness.c H_ZEPHYR MSG_LEN=8 OFF=0 -- $LIBS/zephyr/subsys/crc/crc32_sw.c"
  "e|crcany crc32iso_hdlc_word: depends on c^w only|word_lemma.c LEMMA_LIB -- $W"
  "f|reference: depends on c^w only|word_lemma.c LEMMA_REF -- $W"
  "g|crcany crc32iso_hdlc_bit, 1 byte|harness.c H_CRCANY_BIT MSG_LEN=1 OFF=0 -- $W"
  "h|crcany crc32iso_hdlc_bit, 8 bytes|harness.c H_CRCANY_BIT MSG_LEN=8 OFF=0 -- $W"
  "i|zlib crc32, 24 bytes at offset 0|harness.c H_ZLIB MSG_LEN=24 OFF=0 -- $LIBS/zlib/crc32.c"
  "j|zlib crc32, 24 bytes at offset 1|harness.c H_ZLIB MSG_LEN=24 OFF=1 -- $LIBS/zlib/crc32.c"
  "k|control: one input of 2^40 wrong (must fail)|harness.c H_CONTROL MSG_LEN=1 OFF=0 -- $W"
  "l|control of the c^w lemma (must fail)|word_lemma.c LEMMA_CONTROL -- $W"
  "o|zlib 40 bytes: crc32 is its tables' formula|braid_formula.c UNWIND=12 --"
  "p|reference 40 bytes: a chain of 4-byte steps|braid_ref.c UNWIND=42 --"
  "q|zlib = reference, 40 bytes, 0 and 352 bits|braid_onehot.c UNWIND=42 -- $Z"
  "r|zlib 60 bytes: crc32 is its tables' formula|braid_formula.c BLOCKS=3 UNWIND=17 --"
  "s|reference 60 bytes: a chain of 4-byte steps|braid_ref.c WORDS=15 UNWIND=62 --"
  "t|zlib = reference, 60 bytes, 0 and 512 bits|braid_onehot.c WORDS=15 UNWIND=62 -- $Z"
  "u|control of the formula, 40 bytes (must fail)|braid_formula.c CONTROL UNWIND=12 --"
  "v|control of the chain, 40 bytes (must fail)|braid_ref.c CONTROL UNWIND=42 --"
  "w|control of the single bits, 40 bytes (must fail)|braid_onehot.c CONTROL UNWIND=42 -- $Z"
)
for e in "${L[@]}"; do
    IFS='|' read -r id label args <<<"$e"
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
    # shellcheck disable=SC2086
    prove "$id" "$label" $args &
done
wait
exhaustive m "crcany word = reference, all 2^32 c^w" ""
exhaustive n "control: one of 2^32 wrong (must find 1)" "-DCONTROL"
linear x "braid, crc_word, ref step: linear, all 2^32" ""
linear y "control of linear (must find 1 in each)" "-DCONTROL"
tables z "zlib's tables and crc_word: host = board"
for e in "${L[@]}" "m|" "n|" "x|" "y|" "z|"; do cat "$TMP/${e%%|*}.line"; done
