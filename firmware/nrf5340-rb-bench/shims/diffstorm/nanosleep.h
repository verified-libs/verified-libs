/* diffstorm/cb's cb.c calls nanosleep() (POSIX) in its timeout helpers, but
 * newlib for arm-none-eabi does not declare it. Declare it so cb.c compiles;
 * the helpers are unused here and removed by --gc-sections, so nanosleep is
 * never linked. */
#include <time.h>
int nanosleep(const struct timespec *req, struct timespec *rem);
