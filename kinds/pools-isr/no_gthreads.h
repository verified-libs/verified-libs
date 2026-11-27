/* For MemoryPool in the host check (contract.c): its src/Fixed.h takes a
 * std::mutex in every call only #if _GLIBCXX_HAS_GTHREADS, which glibc's
 * libstdc++ defines and arm-none-eabi's does not. On the boards the pool
 * therefore has no lock. In this check an interrupt that took the mutex while
 * main holds it would wait forever, which is the host's doing, not the
 * pool's; so the check builds it as the boards do: this header is included
 * first (-include), takes in libstdc++'s configuration and removes the macro
 * before Fixed.h tests it. Fixed.h itself is not changed. */
#include <cstddef>
#undef _GLIBCXX_HAS_GTHREADS
