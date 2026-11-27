/* What we saw of MemoryPool's only release, v0.1.0 (c98ff35, the lock entry
 * "memorypool"): does MemoryPool::Fixed<4, 32> hand out blocks 32 bytes apart?
 * Run with `make memorypool-v010` (host g++, in the toolchain image). At
 * v0.1.0 the pool is 80 bytes, its blocks lie 8 bytes apart, and filling block
 * 0's 32 bytes changes block 1; at the head the kind measures (5073178) the
 * blocks lie 32 bytes apart and block 1 is not changed. */
#include <cstdio>
#include "Fixed.h"
int main()
{
    static MemoryPool::Fixed<4, 32> pool;
    unsigned char *b[4];
    for (int i = 0; i < 4; i++) b[i] = static_cast<unsigned char *>(pool.malloc());
    std::printf("sizeof(pool) = %zu (4 blocks of 32 would need at least 128)\n", sizeof(pool));
    for (int i = 0; i < 4; i++) std::printf("block %d at offset %td\n", i, b[i] - b[0]);
    unsigned char before[32];
    for (int i = 0; i < 32; i++) before[i] = b[1][i];
    for (int i = 0; i < 32; i++) b[0][i] = 0xAA;
    int changed = 0;
    for (int i = 0; i < 32; i++) changed += b[1][i] != before[i];
    std::printf("bytes of block 1 changed by filling block 0: %d of 32\n", changed);
    return 0;
}
