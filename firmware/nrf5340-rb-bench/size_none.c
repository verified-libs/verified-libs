/* size.sh: the reference firmware, the harness with no library. In a file
 * of its own so that the compiler cannot see in main.c that every entry is
 * NULL and drop the harness. */
#include "bench.h"
const rb_adapter adapter_none = {0};
