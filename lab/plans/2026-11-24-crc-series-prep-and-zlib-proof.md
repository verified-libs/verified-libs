# CRC kind: before the series, and zlib's braided loop proven in parts

2026-11-24. Branch `kind-crc` at c5d1121. Nothing here uses a board. Part 1
is what has to be in place before the first series is run; part 2 is a plan
for a proof of zlib's braided loop, after the direct try did not finish
(`kinds/crc/README.md`, step 5).

## Part 1: before the series

### 1.1 Review of the record writer, the export rule and the record check

Read on 2026-11-24: `kinds/crc/bench/crcrecords.py`, `test_crcrecords.py`,
`crcverify.sh`, and the CRC part of `lab/tools/public-export.py` with
`lab/tools/test-public-export.sh`. Both test sets pass (9 of 9, 7 of 7).

**The source list of the export rule is whole.** Traced from the build and
the runner: `onecrc.py` imports `onebundle.py` and reads
`firmware/common/<board>/board.mk` and its linker script; `crcslots.py`
imports `oneslots.py`; `run-crc.py` loads `run-one.py`, which imports
`decode.py` and reads `lab/boards.conf`; `onebuild.sh` calls
`lab/tools/source-commit.sh`. All of these are in `CRC_TEST_SOURCES`. None
of the files in `CRC_NOT_SOURCES` is named by a file the build or the runner
uses.

**Record writer: four gaps**, each tried with made-up run files in a
temporary directory (a record was written, exit 0, in every case):

1. A field that is missing in every run of a configuration becomes `null`
   in the record: the comparison is `r.get(k) != runs[0].get(k)`, and
   nothing is not different from nothing. Tried with no `layout` in any run.
   To do: every field of `COMMON` and `IMAGE` must be there and not `None`.
2. A set with one pass per placement gives a record with `"passes": 1`. The
   series is two passes (decided 2026-11-23,
   `2026-11-22-bench-image-per-library.md`). To do: the passes must be
   exactly 1 and 2; a smoke run of one pass can then never become a record.
3. The writer relies on the runner's `invalid` mark alone. A run file with
   `errors` not 0 and no mark is taken (tried with 3 errors in the
   baseline). To do: refuse a run whose `libs[0]["errors"]` or
   `libs[1]["errors"]` is not 0, and one whose `libs[0]["name"]` is not
   `baseline` or whose `libs[1]["name"]` is not the run's `name`.
4. Only `bench_commit` is compared between a run and the `build.json` next
   to it. A run with another `toolchain_image` is taken, and the record then
   holds the run's image name beside the other build's `toolchain` details.
   To do: `toolchain_image` must be the same, and the run's board (through
   `BOARD_DIR[board_id]`) must be the `board` of `build.json`.

One test case each in `test_crcrecords.py` (13 cases then).

**Record check (`crcverify.sh`): nothing that changes a verdict.** One small
point: if the comparing Python program stops with an error, its exit code 1
is counted as "one did not match"; it should count as 2, "could not be
checked".

**Export rule: one consequence to know before the series.** Every file
under `kinds/crc` counts as a test source, a new one too, except
documentation and the list in `CRC_NOT_SOURCES`; and there is no rebuild
ledger for the kind yet. So the first change in `kinds/crc` after the series
(a fix in `crcrecords.py` or `crcverify.sh`, the repeat script of the kind,
a new library) stops the export of all 120 records, until either the series
is measured again or a ledger rule for the kind exists. The check a ledger
would rest on is there already (`VL_TREE=1 bash crcverify.sh`: does this
tree still build the images the records were measured from?). To do now:
bring everything that is planned for `kinds/crc` in before the series
(points 1 to 4, 1.2, the repeat script). To do before publication, if a
change came after the series anyway: the ledger rule, as its own decision.
The proofs (`proof/`) and the README are not test sources, so part 2 can be
done before or after the series without touching a record.

### 1.2 The Pico 2 is written in parts

`run-crc.py --flash` writes a bundle in one `probe-rs download`. The Pico
2's bundle is 505 units of 4096 bytes (about 2 MB); in this lab a write of
more than about 45 seconds in one piece does not get through on that board
(the hub port is power cycled at 65 seconds). To do: for `rp2350`, write a
bundle of more than 250 units in parts of at most 250 units, each part
verified, then the whole bundle verified as now; the way of the far-call
series of version 2 (a helper kept outside the repository) carried into the
runner. Every other board is written as now. It counts as one write of the
flash, as in that series.

### 1.3 Order

1. The changes of 1.1 and 1.2, and the repeat script of the kind (a copy of
   version 2's `repeat.sh` for `run-crc.py`), committed.
2. All six tables built again at that commit, clean (`onebuild.sh table`);
   `test_crcrecords.py`, `test-public-export.sh`, and `crcverify.sh` on a
   record made from made-up runs of that build.
3. The smoke test: every step, shrunk, never skipped, the Pico 2's write in
   parts among them.
4. The series (26 writes of flash), on the owner's word.

## Part 2: zlib's braided loop, proven in parts

### 2.1 Where it stands

zlib 1.4 (commit 99623ef, `crc32.c`) on a 32-bit ARM core takes 4-byte
words (W = 4) in five braids (N = 5). From 23 bytes on it works in blocks of
20 bytes: `blks = len / 20`, a loop `while (--blks)` that looks each braid's
word up in `crc_braid_table`, and a last block that is combined with
`crc_word()`. The proof in `run.sh` (24 bytes) goes through the last block
only; the loop does not run. A direct proof of 40 bytes, where it runs once,
did not finish in 60 minutes.

### 2.2 The idea

Over GF(2), a CRC is an affine function of its input bits (the start value
and the message): linear but for a constant. Two affine functions that agree
at the zero input and at every input with exactly one bit set agree
everywhere. For 40 bytes that is 1 + 352 inputs instead of 2^352. What has
to be shown is that both sides are affine, and that is done by showing each
of them to be a fixed composition of XOR and of three functions of 32 bits
whose linearity can be computed for all 2^32 values.

For x = (c, w0 ... w9), c the start value and w the ten message words:

| | what | how |
|---|---|---|
| A | `crc32_z(c, w, 40)` = F(x), where F is written with zlib's own tables: XOR, the complement of c, `braid()` (the four lookups in `crc_braid_table`) and `crc_word()` | CBMC, every x |
| B | `braid()`, `crc_word()` and S (the reference over four zero bytes) are linear: f(x) is the XOR of f at the set bits of x | computed on the host, all 2^32 values of each |
| C | `ref32_update(r, w, 40)` = S(...S(S(r ^ w0) ^ w1)... ^ w9) | CBMC, every r and w |
| D | zlib = reference at x = 0 and at each of the 352 inputs with one bit set | CBMC, 353 inputs |
| E | A and B make zlib's side affine, C and B the reference's; with D they are the same function | argued, not machine-checked |

The table of A and B must be the one the boards use: B is built by the
host's compiler with `-DZ_TESTW=4`, A is preprocessed for the Cortex-M4. So
a further check, F: the initialisers of `crc_table` and `crc_braid_table`
are the same text in both preprocessed files.

### 2.3 Tried on 2026-11-24

In the toolchain image, the sources preprocessed as in `run.sh`, 900 seconds
allowed per try, four at a time:

| try | unwind | result | seconds |
|---|---|---|---|
| A, 40 bytes | 12 | proven | 158 |
| A, 60 bytes (the loop runs twice) | 17 | proven | 248 |
| A, 40 bytes, control | 12 | fails, as it must | 96 |
| C, 40 bytes | 42 | proven | 234 |
| C in two steps: 40 bytes = ten calls of 4 bytes | 42 | proven | 227 |
| D, 40 bytes | 42 | proven | 163 |
| D, 40 bytes, control | 42 | fails, as it must | 163 |
| B, three functions, all 2^32 | | 0 not the sum of their bits | 36 |
| B, control | | finds its 1 wrong value in each | |

C goes through directly, so the two-step way is not needed. (A try of the
second step of that way, one word against four zero bytes, stopped at an
unwinding assertion: unwind 6 was too low for it. It was not tried again.)
Not tried: C and D for 60 bytes, and F.

### 2.4 To build

All in `kinds/crc/proof/` and the README; no file outside them.

- `run.sh`: `prove` takes an unwind value per proof. A token `UNWIND=N`
  among the defines sets it; without one it is 34, so the lines a to l run
  the commands they run now. A function `linear` beside `exhaustive` for B
  (`gcc -O2 -pthread -DZ_TESTW=4`, with `-I$LIBS/zlib`), and the check F.
- Three harnesses and one host program, below as they were tried. A control
  for C is to be added (`CONTROL`: one wrong result, must fail).
- New lines, each with its time and verdict as the others:
  - zlib, 40 bytes: `crc32_z` is the formula of its tables (A)
  - reference, 40 bytes: a chain of steps over four zero bytes (C)
  - zlib = reference at zero and at 352 single bits, 40 bytes (D)
  - the same three for 60 bytes (`BLOCKS=3`, `WORDS=15`, unwind 17 and 62)
  - the controls of A, C and D (must fail)
  - braid, `crc_word`, reference step: linear, all 2^32 (B), and its control
  - the tables are the same for the host and the board (F)
- The 60-minute limit stays. A part that does not finish is reported as
  that, and then that length is not called proven.

### 2.5 What the README may say

Not "proven" alone. The row for zlib names the lengths (40 and 60 bytes at
offset 0, every start value, every message) and says "proven in parts": A, C
and D by CBMC, B computed for all 2^32 values, E argued. E is written out in
the README in full, as in 2.2, with what it rests on that no tool checked:
the step from "affine and equal at 353 inputs" to "equal", and that the host
compiler and CBMC's ARM model give the same values for the three functions
of B (unsigned 32-bit arithmetic and table lookups only; F covers the
tables). The sentence of c5d1121 about the direct try stays, with the split
as what came after it. Lengths between, other offsets and other word sizes
stay tested, not proven.

### 2.6 The sources as tried

`braid_formula.c` (A; no library file on the line, it includes `crc32.c`):

```c
#include <stddef.h>
#include <stdint.h>
#include "crc32.c"
uint32_t nondet_u32(void);
#ifndef BLOCKS
#define BLOCKS 2
#endif
static uint32_t braid(uint32_t x)
{
    return crc_braid_table[0][x & 0xff] ^ crc_braid_table[1][(x >> 8) & 0xff] ^
           crc_braid_table[2][(x >> 16) & 0xff] ^ crc_braid_table[3][(x >> 24) & 0xff];
}
static uint32_t w[5 * BLOCKS];
int main(void)
{
    uint32_t c = nondet_u32();
    for (int i = 0; i < 5 * BLOCKS; i++) w[i] = nondet_u32();
    uint32_t got = (uint32_t)crc32_z(c, (const unsigned char *)w, 20 * BLOCKS);
    uint32_t b[5] = { ~c, 0, 0, 0, 0 };
    const uint32_t *p = w;
    for (int k = 1; k < BLOCKS; k++, p += 5)
        for (int i = 0; i < 5; i++) b[i] = braid(b[i] ^ p[i]);
    uint32_t x = 0;
    for (int i = 0; i < 5; i++) x = crc_word(b[i] ^ p[i] ^ x);
#ifdef CONTROL
    x ^= (c == 0x12345678u && w[7] == 0x9ABCDEF0u);
#endif
    __CPROVER_assert(got == ~x, "crc32_z is the formula of its tables");
    return 0;
}
```

`braid_ref.c` (C; with `../ref_crc.c`):

```c
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"
uint32_t nondet_u32(void);
#ifndef WORDS
#define WORDS 10
#endif
static uint32_t w[WORDS], z4[1];
int main(void)
{
    uint32_t r = nondet_u32();
    for (int i = 0; i < WORDS; i++) w[i] = nondet_u32();
    uint32_t x = r;
    for (int i = 0; i < WORDS; i++) x = ref32_update(x ^ w[i], z4, 4);
    __CPROVER_assert(ref32_update(r, w, 4 * WORDS) == x, "the reference is a chain of steps over four zero bytes");
    return 0;
}
```

`braid_onehot.c` (D; with `../ref_crc.c` and zlib's `crc32.c`):

```c
#include <stddef.h>
#include <stdint.h>
#include "ref_crc.h"
#include "zlib.h"
unsigned nondet_unsigned(void);
#ifndef WORDS
#define WORDS 10
#endif
static uint32_t w[WORDS];
int main(void)
{
    unsigned i = nondet_unsigned();
    __CPROVER_assume(i <= 32 + 32 * WORDS);
    uint32_t c = 0;
    if (i < 32) c = (uint32_t)1 << i;
    else if (i < 32 + 32 * WORDS) w[(i - 32) / 32] = (uint32_t)1 << ((i - 32) % 32);
    uint32_t got = (uint32_t)crc32(c, (const unsigned char *)w, 4 * WORDS);
#ifdef CONTROL
    got ^= (i == 200);
#endif
    uint32_t want = ref32_final(ref32_update(c ^ 0xFFFFFFFFu, w, 4 * WORDS));
    __CPROVER_assert(got == want, "equal at zero and at every single bit");
    return 0;
}
```

`braid_linear.c` (B; host, `-DZ_TESTW=4`, with `../ref_crc.c`):

```c
#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>
#include "crc32.c"
#include "ref_crc.h"
static uint32_t f_braid(uint32_t x)
{
    return crc_braid_table[0][x & 0xff] ^ crc_braid_table[1][(x >> 8) & 0xff] ^
           crc_braid_table[2][(x >> 16) & 0xff] ^ crc_braid_table[3][(x >> 24) & 0xff];
}
static uint32_t f_word(uint32_t x) { return crc_word(x); }
static uint32_t f_ref(uint32_t x) { static const uint32_t z[1] = {0}; return ref32_update(x, z, 4); }
static uint32_t (*const F[3])(uint32_t) = { f_braid, f_word, f_ref };
static const char *const NAME[3] = { "braid", "crc_word", "reference, four zero bytes" };
static uint32_t M[4][256];   /* the function as the sum of its values at the 32 single bits */
static uint32_t (*f)(uint32_t);
struct part { uint64_t lo, hi, bad; };
static void *run(void *arg)
{
    struct part *p = arg;
    for (uint64_t i = p->lo; i < p->hi; i++) {
        uint32_t x = (uint32_t)i, got = f(x);
#ifdef CONTROL
        got ^= (x == 0x12345678u);
#endif
        p->bad += got != (M[0][x & 0xff] ^ M[1][(x >> 8) & 0xff] ^ M[2][(x >> 16) & 0xff] ^ M[3][x >> 24]);
    }
    return NULL;
}
int main(void)
{
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    if (n > 64) n = 64;
    int rc = 0;
    for (int which = 0; which < 3; which++) {
        f = F[which];
        for (int k = 0; k < 4; k++)
            for (int v = 0; v < 256; v++) {
                M[k][v] = 0;
                for (int j = 0; j < 8; j++) if (v >> j & 1) M[k][v] ^= f((uint32_t)1 << (8 * k + j));
            }
        struct part parts[64] = {0}; pthread_t t[64]; uint64_t bad = 0;
        for (long k = 0; k < n; k++) {
            parts[k].lo = ((uint64_t)1 << 32) * k / n; parts[k].hi = ((uint64_t)1 << 32) * (k + 1) / n;
            pthread_create(&t[k], NULL, run, &parts[k]);
        }
        for (long k = 0; k < n; k++) { pthread_join(t[k], NULL); bad += parts[k].bad; }
        printf("%s: 4294967296 values, %" PRIu64 " not the sum of its bits\n", NAME[which], bad);
        rc |= bad != 0;
    }
    return rc;
}
```
