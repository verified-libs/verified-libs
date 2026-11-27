/* Eclipse ThreadX block pool (common/src/tx_block_*.c), pinned in
 * libs.lock, run alone without ThreadX's scheduler: the pool's own files, a
 * port header (ports/host/tx_port.h on the host; the release's
 * ports/cortex_mN/gnu/inc/tx_port.h on a board) and stubs for the scheduler
 * calls the pool makes only when a thread waits (tx_kernel_stubs.c). Every
 * call is made with TX_NO_WAIT, the one option ThreadX documents for an ISR,
 * so no thread ever waits (the pilot, pilot/pools/README.md). */
#define TX_DISABLE_ERROR_CHECKING
#include "pool.h"
#include "tx_api.h"

/* ThreadX keeps a pointer in front of every block (tx_block_pool_create.c:
 * pool_size / (block_size + sizeof(UCHAR *)) blocks). */
#define TX_POOL_BYTES (POOL_BLOCKS * (POOL_BLOCK_SIZE + sizeof(UCHAR *)))
static POOL_GUARDED(TX_BLOCK_POOL pool; ULONG area[TX_POOL_BYTES / sizeof(ULONG)];) g;

static void tx_init(void)
{
    if (g.pool.tx_block_pool_id) tx_block_pool_delete(&g.pool);
    tx_block_pool_create(&g.pool, (CHAR *)"vl pools", POOL_BLOCK_SIZE, g.area, sizeof(g.area));
}
static uintptr_t tx_alloc(uintptr_t a, uintptr_t b)
{
    (void)a; (void)b;
    VOID *p = 0;
    return tx_block_allocate(&g.pool, &p, TX_NO_WAIT) == TX_SUCCESS ? (uintptr_t)p : 0;
}
static uint32_t tx_free(uintptr_t a, uintptr_t b) { (void)b; return tx_block_release((VOID *)a) == TX_SUCCESS; }
static void tx_region(uintptr_t *lo, uintptr_t *hi) { *lo = (uintptr_t)g.area; *hi = (uintptr_t)g.area + sizeof(g.area); }

const pool_adapter adapter_threadx = {
    "ThreadX block pool (C)", tx_init, tx_alloc, tx_free, tx_region, sizeof(void *), g.canary_lo, g.canary_hi
};
