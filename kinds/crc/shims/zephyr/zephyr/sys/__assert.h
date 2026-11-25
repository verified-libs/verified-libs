/* What zephyr/sys/crc.h needs of Zephyr's assertions when built alone (CRC
 * kind): __ASSERT_NO_MSG, used only by the inline crc_by_type(), which the
 * adapters do not call. Assertions off, as in a release build of Zephyr. */
#pragma once
#define __ASSERT_NO_MSG(test) ((void)0)
