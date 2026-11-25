/* What subsys/crc needs of zephyr/types.h when built alone (CRC kind): the
 * fixed-width integer types, and __weak, which Zephyr's toolchain headers
 * define as the weak attribute. */
#pragma once
#include <stdint.h>
#ifndef __weak
#define __weak __attribute__((__weak__))
#endif
