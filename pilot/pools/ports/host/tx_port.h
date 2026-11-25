/* Pilot: a ThreadX port header for running the block pool alone on the
 * host, without ThreadX's scheduler (README.md, "ThreadX without its
 * kernel"). Written for this pilot after ports/cortex_m4/gnu/inc/tx_port.h
 * of the pinned release; only what the block pool's files need.
 * "Interrupts off" is a flag of the test (pilot_irq_*), as the contract
 * check's host_irq.h does it, so a later host model can preempt here. */
#ifndef TX_PORT_H
#define TX_PORT_H

#include <stdlib.h>
#include <string.h>

#define VOID                                    void
typedef char                                    CHAR;
typedef unsigned char                           UCHAR;
typedef int                                     INT;
typedef unsigned int                            UINT;
typedef int                                     LONG;      /* 32 bits, as on the target */
typedef unsigned int                            ULONG;
typedef unsigned long long                      ULONG64;
typedef short                                   SHORT;
typedef unsigned short                          USHORT;
#define ULONG64_DEFINED

#define TX_MAX_PRIORITIES                       32
#define TX_MINIMUM_STACK                        200
#define TX_TIMER_THREAD_STACK_SIZE              1024
#define TX_TIMER_THREAD_PRIORITY                0
#define TX_INT_DISABLE                          1
#define TX_INT_ENABLE                           0
#define TX_TRACE_TIME_SOURCE                    0
#define TX_TRACE_TIME_MASK                      0xFFFFFFFFUL
#define TX_PORT_SPECIFIC_BUILD_OPTIONS          (0)
#define TX_INLINE_INITIALIZATION

#define TX_THREAD_EXTENSION_0
#define TX_THREAD_EXTENSION_1
#define TX_THREAD_EXTENSION_2
#define TX_THREAD_EXTENSION_3
#define TX_BLOCK_POOL_EXTENSION
#define TX_BYTE_POOL_EXTENSION
#define TX_EVENT_FLAGS_GROUP_EXTENSION
#define TX_MUTEX_EXTENSION
#define TX_QUEUE_EXTENSION
#define TX_SEMAPHORE_EXTENSION
#define TX_TIMER_EXTENSION
#define TX_THREAD_USER_EXTENSION
#define TX_THREAD_CREATE_EXTENSION(thread_ptr)
#define TX_THREAD_DELETE_EXTENSION(thread_ptr)
#define TX_THREAD_COMPLETED_EXTENSION(thread_ptr)
#define TX_THREAD_TERMINATED_EXTENSION(thread_ptr)
#define TX_BLOCK_POOL_CREATE_EXTENSION(pool_ptr)
#define TX_BYTE_POOL_CREATE_EXTENSION(pool_ptr)
#define TX_EVENT_FLAGS_GROUP_CREATE_EXTENSION(group_ptr)
#define TX_MUTEX_CREATE_EXTENSION(mutex_ptr)
#define TX_QUEUE_CREATE_EXTENSION(queue_ptr)
#define TX_SEMAPHORE_CREATE_EXTENSION(semaphore_ptr)
#define TX_TIMER_CREATE_EXTENSION(timer_ptr)
#define TX_BLOCK_POOL_DELETE_EXTENSION(pool_ptr)
#define TX_BYTE_POOL_DELETE_EXTENSION(pool_ptr)
#define TX_EVENT_FLAGS_GROUP_DELETE_EXTENSION(group_ptr)
#define TX_MUTEX_DELETE_EXTENSION(mutex_ptr)
#define TX_QUEUE_DELETE_EXTENSION(queue_ptr)
#define TX_SEMAPHORE_DELETE_EXTENSION(semaphore_ptr)
#define TX_TIMER_DELETE_EXTENSION(timer_ptr)

UINT pilot_irq_disable(void);
void pilot_irq_restore(UINT);
#define TX_INTERRUPT_SAVE_AREA                  UINT interrupt_save;
#define TX_DISABLE                              interrupt_save = pilot_irq_disable();
#define TX_RESTORE                              pilot_irq_restore(interrupt_save);


#ifdef TX_THREAD_INIT
CHAR _tx_version_id[] = "pilot host port for the ThreadX block pool";
#else
extern CHAR _tx_version_id[];
#endif

#endif
