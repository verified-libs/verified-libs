/* GenMC shim: glibc's <sys/types.h> pulls in <bits/pthreadtypes.h>, whose
 * pthread types clash with those of GenMC's own <pthread.h>. This file is
 * found first (verify/genmc/shims leads the include path) and declares the
 * types exactly as GenMC's pthread.h does (identical typedefs may repeat).
 * It must not include <pthread.h> itself: that includes <stdio.h>, which may
 * be the header that is including us. Types GenMC does not model get
 * placeholders; the queues under test never use them. */
#ifndef VL_GENMC_PTHREADTYPES_SHIM
#define VL_GENMC_PTHREADTYPES_SHIM
#include <genmc_internal.h>
typedef __VERIFIER_attr_t pthread_attr_t;
typedef __VERIFIER_barrier_t pthread_barrier_t;
typedef __VERIFIER_barrierattr_t pthread_barrierattr_t;
typedef __VERIFIER_mutex_t pthread_mutex_t;
typedef __VERIFIER_mutexattr_t pthread_mutexattr_t;
typedef __VERIFIER_rwlock_t pthread_rwlock_t;
typedef __VERIFIER_rwlockattr_t pthread_rwlockattr_t;
typedef __VERIFIER_thread_t pthread_t;
/* not modelled by GenMC */
typedef long pthread_cond_t;
typedef long pthread_condattr_t;
typedef int pthread_key_t;
typedef int pthread_once_t;
typedef struct { int __private; } pthread_spinlock_t;
#endif
