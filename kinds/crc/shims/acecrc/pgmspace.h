/* AceCRC reads its tables with the AVR pgmspace macros and includes
 * <pgmspace.h> on cores other than AVR and SAMD (src/ace_crc/*.cpp). On an ARM
 * core flash is in the address space: PROGMEM is empty and a read is a plain
 * load, which is what the Arduino cores for ARM define (CRC kind). */
#pragma once
#include <stdint.h>
#define PROGMEM
#define pgm_read_byte(p)  (*(const uint8_t *)(p))
#define pgm_read_word(p)  (*(const uint16_t *)(p))
#define pgm_read_dword(p) (*(const uint32_t *)(p))
