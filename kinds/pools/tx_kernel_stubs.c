/* What ThreadX's block pool needs from the rest of ThreadX when it is run
 * alone (adapter_threadx.c). The scheduler calls are reached only on
 * the paths where a thread waits for a block or is woken; with TX_NO_WAIT
 * and no threads they are never reached, and each stops the program if it
 * is (the preemption check, which delete always calls, does nothing). The variables are those of tx_thread_initialize.c, zero: no thread
 * is running, the system is "initialised". */
#include <stdlib.h>
#include "tx_api.h"
/* Stop: abort() on the host; a loop on a board, so that the stubs bring no
 * C library code of their own into the image (they are never reached). */
#if defined(__arm__)
#define STOP() for (;;) {}
#else
#define STOP() abort()
#endif
#include "tx_thread.h"
#include "tx_block_pool.h"

volatile ULONG _tx_thread_system_state;
TX_THREAD *_tx_thread_current_ptr;
volatile UINT _tx_thread_preempt_disable;

/* The block pool's list of created pools (tx_block_pool.h). With in-line
 * initialisation (the ports' TX_INLINE_INITIALIZATION) ThreadX defines them
 * with the rest of its globals in tx_initialize_high_level.c, which the
 * kind does not build. */
TX_BLOCK_POOL *_tx_block_pool_created_ptr;
ULONG _tx_block_pool_created_count;

/* Called by tx_block_pool_delete() after it has woken any waiting thread:
 * with no threads there is nothing to preempt. */
VOID _tx_thread_system_preempt_check(VOID) {}

VOID _tx_thread_system_suspend(TX_THREAD *t) { (void)t; STOP(); }
VOID _tx_thread_system_resume(TX_THREAD *t) { (void)t; STOP(); }
VOID _tx_thread_system_ni_suspend(TX_THREAD *t, ULONG timeout) { (void)t; (void)timeout; STOP(); }
VOID _tx_thread_system_ni_resume(TX_THREAD *t) { (void)t; STOP(); }
VOID _tx_block_pool_cleanup(TX_THREAD *t, ULONG suspension_sequence) { (void)t; (void)suspension_sequence; STOP(); }
