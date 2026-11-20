/*
 * Demonstration: diffstorm/cb (547d0812f30d) reads the 1-byte `overwrite`
 * flag with a 32-bit load, so uninitialised padding after it can turn on
 * overwrite mode that was never enabled.
 *
 * cb_init_ex() stores `overwrite` with a 1-byte atomic store, but
 * cb_insert_ex() (cb.c:373) reads it with CB_ATOMIC_LOAD, which always casts
 * to a 32-bit atomic. The 3 padding bytes after `overwrite` are never
 * initialised. If the memory holding the `cb` object was not zero, a full
 * buffer then overwrites the oldest item instead of rejecting the insert,
 * and the producer moves `out`, which belongs to the consumer.
 *
 * The same object is tested twice: in zeroed memory (correct behaviour) and
 * in memory that held 0xAA before (as a stack object or reused buffer may).
 * Overwrite mode is never enabled in either case.
 */
#include <stdio.h>
#include <string.h>
#include "cb.h"

static int run(const char *label, unsigned char fill)
{
    union { cb c; unsigned char raw[sizeof(cb)]; } mem;
    memset(mem.raw, fill, sizeof mem.raw);      /* previous memory contents */

    CbItem storage[4];
    cb_init(&mem.c, storage, 4);                /* 3 usable slots */

    int ok = 1;
    for (CbItem v = 1; v <= 3; v++) ok &= cb_insert(&mem.c, v);
    int fourth = cb_insert(&mem.c, 4);          /* buffer full: must fail */
    CbItem first = 0;
    cb_remove(&mem.c, &first);                  /* must be 1 */

    printf("%-28s overwrite flag=%d  insert into full buffer=%s  first item=%u  -> %s\n",
           label, (int)cb_get_overwrite(&mem.c), fourth ? "accepted" : "rejected",
           (unsigned)first, (!fourth && first == 1 && ok) ? "correct" : "WRONG");
    return !fourth && first == 1 && ok;
}

int main(void)
{
    printf("sizeof(cb)=%zu, offsetof(overwrite)=%zu, sizeof(overwrite)=%zu\n",
           sizeof(cb), offsetof(cb, overwrite), sizeof(((cb *)0)->overwrite));
    int a = run("zeroed memory:", 0x00);
    int b = run("memory that held 0xAA:", 0xAA);
    return (a && !b) ? 0 : 1;                   /* 0 = bug reproduced as described */
}
