/* Shim for contiki.h, so os/lib/ringbuf.c can be built outside Contiki-NG.
 * ringbuf only needs stdint types and CC_ACCESS_NOW, which comes from
 * Contiki's own os/sys/cc.h (used unchanged). */
#ifndef CONTIKI_H_
#define CONTIKI_H_
#include <stdint.h>
#endif
