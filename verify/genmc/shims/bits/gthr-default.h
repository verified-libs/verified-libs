/* GenMC shim: libstdc++ normally uses its POSIX thread layer (gthr-posix.h)
 * for internal locks (shared_ptr, locale, ...). GenMC's own pthread.h has
 * only what GenMC models, so that layer does not compile. The queues under
 * test use std::atomic only, not these internal locks, so libstdc++'s
 * single-threaded layer is used instead. This file is found before the
 * system one because verify/genmc/shims comes first on the include path. */
#include <bits/gthr-single.h>
