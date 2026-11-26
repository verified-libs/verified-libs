/* The boards' CRC hardware, driven by our code: not a library. Rows of
 * reference, as the bitwise reference (ref_crc.c) is (DECISIONS 2026-11-25,
 * lab/plans/2026-11-25-crc-hw-and-ram-series.md). Built for the boards whose
 * unit computes the CRC (kinds/crc/boards.txt); on another board this file
 * defines nothing. Every call's result is compared with the reference on the
 * board (bench/main.c), so a wrong setting shows there.
 *
 * NUCLEO-G474RE, NUCLEO-G0B1RE, NUCLEO-H723ZG: the CRC calculation unit
 * (RM0440 Rev 9 section 16, RM0444 Rev 6 section 14, RM0468 Rev 3 section
 * 21). init() enables its clock and sets the polynomial size, the polynomial
 * and the initial value once; a call resets the unit to the initial value
 * (CRC_CR.RESET) and writes the message to CRC_DR: single bytes up to a word
 * boundary, then words, then the last bytes. Input reversal by byte
 * (REV_IN = 01) for CRC-32, none for the others; a word is written with its
 * bytes swapped (the unit takes a word from its most significant byte, the
 * message is in memory order). CRC-32/ISO-HDLC: output reversal (REV_OUT),
 * and the final XOR with 0xFFFFFFFF is done here: the unit has no output XOR.
 *
 * Raspberry Pi Pico 2: the DMA sniffer (RP2350 datasheet RP-008373,
 * 12.6.8.2, SNIFF_CTRL). init() takes the DMA out of reset; a call sets the
 * seed and the sniffer, moves the message with DMA channel 0 in single bytes
 * (any length and start) to one dummy byte in RAM, waits for the channel and
 * reads the result. CRC-32/ISO-HDLC: CALC = CRC32R (bit-reversed data), seed
 * 0xFFFFFFFF, the result read bit-reversed and inverted (OUT_REV, OUT_INV).
 * CRC-16/IBM-3740: CALC = CRC16 (CRC-16-CCITT, MSB first), seed 0xFFFF, the
 * low 16 bits. The sniffer has no 8-bit CRC. */
#include "crc.h"
#if __has_include("board.h")
#include "board.h"
#endif

#ifndef BOARD_ID
#define BOARD_ID 0u
#endif

#define HW_REG(a)  (*(volatile uint32_t *)(uintptr_t)(a))
#define HW_REG8(a) (*(volatile uint8_t *)(uintptr_t)(a))

#if BOARD_ID == 2u || BOARD_ID == 3u || BOARD_ID == 4u   /* NUCLEO-G0B1RE, NUCLEO-G474RE, NUCLEO-H723ZG */

#if BOARD_ID == 4u
#define HW_CRC      0x58024C00u            /* RM0468: CRC */
#define HW_CLK_REG  (0x58024400u + 0xE0u)  /* RCC_AHB4ENR */
#define HW_CLK_BIT  (1u << 19)             /* CRCEN */
#elif BOARD_ID == 3u
#define HW_CRC      0x40023000u            /* RM0440: CRC */
#define HW_CLK_REG  (0x40021000u + 0x48u)  /* RCC_AHB1ENR */
#define HW_CLK_BIT  (1u << 12)             /* CRCEN */
#else
#define HW_CRC      0x40023000u            /* RM0444: CRC */
#define HW_CLK_REG  (0x40021000u + 0x38u)  /* RCC_AHBENR */
#define HW_CLK_BIT  (1u << 12)             /* CRCEN */
#endif
#define HW_DR    HW_REG(HW_CRC + 0x00u)
#define HW_DR8   HW_REG8(HW_CRC + 0x00u)
#define HW_CR    HW_REG(HW_CRC + 0x08u)
#define HW_INIT  HW_REG(HW_CRC + 0x10u)
#define HW_POL   HW_REG(HW_CRC + 0x14u)
#define CR_RESET    1u
#define CR_SIZE32   (0u << 3)
#define CR_SIZE16   (1u << 3)
#define CR_SIZE8    (2u << 3)
#define CR_REVIN_B  (1u << 5)
#define CR_REVOUT   (1u << 7)

static uint32_t hw_cr;

static void hw_setup(uint32_t cr, uint32_t pol, uint32_t init)
{
    HW_REG(HW_CLK_REG) |= HW_CLK_BIT;
    (void)HW_REG(HW_CLK_REG);              /* the clock is on before the unit is written */
    hw_cr = cr;
    HW_CR = cr;
    HW_POL = pol;
    HW_INIT = init;
}

/* The message into CRC_DR: bytes up to a word boundary, words (bytes swapped), the last bytes. */
static void hw_feed(const uint8_t *p, uintptr_t n)
{
    HW_CR = hw_cr | CR_RESET;              /* CRC_DR = CRC_INIT */
    while (n && ((uintptr_t)p & 3u)) { HW_DR8 = *p++; n--; }
    for (; n >= 4u; n -= 4u, p += 4u) {
        uint32_t w;
        /* p is on a word boundary here. Said to the compiler, so the copy is one load: without
         * it, gcc for the Cortex-M0+ (no unaligned loads) calls the library's memcpy for every
         * word, and the G0B1's rows timed that call, not the unit (the first G0B1 run). */
        __builtin_memcpy(&w, __builtin_assume_aligned(p, 4), 4u);
        HW_DR = __builtin_bswap32(w);
    }
    while (n--) HW_DR8 = *p++;
}

static void hw32_init(void) { hw_setup(CR_SIZE32 | CR_REVIN_B | CR_REVOUT, 0x04C11DB7u, 0xFFFFFFFFu); }
static uint32_t hw32_crc(uintptr_t a, uintptr_t n) { hw_feed((const uint8_t *)a, n); return HW_DR ^ 0xFFFFFFFFu; }
static void hw16_init(void) { hw_setup(CR_SIZE16, 0x1021u, 0xFFFFu); }
static uint32_t hw16_crc(uintptr_t a, uintptr_t n) { hw_feed((const uint8_t *)a, n); return HW_DR & 0xFFFFu; }
static void hw8_init(void) { hw_setup(CR_SIZE8, 0x07u, 0x00u); }
static uint32_t hw8_crc(uintptr_t a, uintptr_t n) { hw_feed((const uint8_t *)a, n); return HW_DR & 0xFFu; }

#define HW_NOTE "the board's CRC unit, driven by our code; not a library"
const crc_adapter adapter_hw_crc32 = { "CRC unit (STM32)", "ours", CRC32_ISO_HDLC, CLS_OTHER, 0, 0,
    HW_NOTE "; the final XOR with 0xFFFFFFFF in our code (the unit has none)", hw32_init, hw32_crc, CRC_STREAM(NULL, NULL, NULL) };
const crc_adapter adapter_hw_crc16 = { "CRC unit (STM32)", "ours", CRC16_IBM_3740, CLS_OTHER, 0, 0,
    HW_NOTE, hw16_init, hw16_crc, CRC_STREAM(NULL, NULL, NULL) };
const crc_adapter adapter_hw_crc8 = { "CRC unit (STM32)", "ours", CRC8_SMBUS, CLS_OTHER, 0, 0,
    HW_NOTE, hw8_init, hw8_crc, CRC_STREAM(NULL, NULL, NULL) };

#elif BOARD_ID == 6u   /* Raspberry Pi Pico 2 */

#define HW_DMA        0x50000000u
#define HW_CH0_READ   HW_REG(HW_DMA + 0x000u)
#define HW_CH0_WRITE  HW_REG(HW_DMA + 0x004u)
#define HW_CH0_COUNT  HW_REG(HW_DMA + 0x008u)
#define HW_CH0_CTRL   HW_REG(HW_DMA + 0x00Cu)  /* CH0_CTRL_TRIG */
#define HW_SNIFF_CTRL HW_REG(HW_DMA + 0x454u)
#define HW_SNIFF_DATA HW_REG(HW_DMA + 0x458u)
#define CTRL_EN       (1u << 0)
#define CTRL_BYTE     (0u << 2)                /* DATA_SIZE: SIZE_BYTE */
#define CTRL_INCR_RD  (1u << 4)
#define CTRL_TREQ_ALL (0x3Fu << 17)            /* TREQ_SEL: permanent request, unpaced */
#define CTRL_SNIFF    (1u << 25)
#define CTRL_BUSY     (1u << 26)
#define SNIFF_EN      (1u << 0)                /* DMACH = 0 */
#define SNIFF_CRC32R  (1u << 5)
#define SNIFF_CRC16   (2u << 5)
#define SNIFF_OUT_REV (1u << 10)
#define SNIFF_OUT_INV (1u << 11)
#define RESETS_DMA    (1u << 2)

static volatile uint8_t hw_sink;

static void hw_dma_on(void)
{
    HW_REG(0x40020000u + 0x3000u) = RESETS_DMA;      /* RESETS_RESET, atomic clear alias */
    while (!(HW_REG(0x40020000u + 0x08u) & RESETS_DMA)) {}   /* RESET_DONE */
}

static uint32_t hw_sniff(uintptr_t a, uintptr_t n, uint32_t sniff, uint32_t seed)
{
    HW_SNIFF_DATA = seed;
    HW_SNIFF_CTRL = sniff;
    HW_CH0_READ = (uint32_t)a;
    HW_CH0_WRITE = (uint32_t)(uintptr_t)&hw_sink;
    HW_CH0_COUNT = (uint32_t)n;
    HW_CH0_CTRL = CTRL_EN | CTRL_BYTE | CTRL_INCR_RD | CTRL_TREQ_ALL | CTRL_SNIFF;
    while (HW_CH0_CTRL & CTRL_BUSY) {}
    return HW_SNIFF_DATA;
}

static void hw32_init(void) { hw_dma_on(); }
static uint32_t hw32_crc(uintptr_t a, uintptr_t n)
{
    return hw_sniff(a, n, SNIFF_EN | SNIFF_CRC32R | SNIFF_OUT_REV | SNIFF_OUT_INV, 0xFFFFFFFFu);
}
static void hw16_init(void) { hw_dma_on(); }
static uint32_t hw16_crc(uintptr_t a, uintptr_t n) { return hw_sniff(a, n, SNIFF_EN | SNIFF_CRC16, 0xFFFFu) & 0xFFFFu; }

#define HW_NOTE "the board's DMA sniffer, driven by our code; not a library"
const crc_adapter adapter_hw_crc32 = { "DMA sniffer (RP2350)", "ours", CRC32_ISO_HDLC, CLS_OTHER, 0, 0,
    HW_NOTE, hw32_init, hw32_crc, CRC_STREAM(NULL, NULL, NULL) };
const crc_adapter adapter_hw_crc16 = { "DMA sniffer (RP2350)", "ours", CRC16_IBM_3740, CLS_OTHER, 0, 0,
    HW_NOTE, hw16_init, hw16_crc, CRC_STREAM(NULL, NULL, NULL) };

#endif
