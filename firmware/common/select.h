/* The selection words of a bundle (common/bundle.py, common/slotboot.c):
 * magic, library index, ~index and a pad word, which the host or the
 * running image writes before a reset and the boot stub and the started
 * image read after it. One fixed place per board and code location, the
 * same in every test firmware, so one boot stub can start an image of any
 * of them:
 *   - the last 16 bytes of RAM (section .select in every linker script; not
 *     cleared at start-up; the stack starts below them), or
 *   - where the board says (BOARD_SELECT_ADDR): the RP2350's boot ROM uses
 *     SRAM at every reset, so there they are kept in the watchdog's scratch
 *     registers (common/rp2350/board_uart.h).
 * The STM32H7 RAM ECC write buffer can lose the last words written before a
 * reset (seen 2026-11-14): a firmware writes the pad word and then other
 * RAM after the selection (vl_select_flush). */
#pragma once
#include <stdint.h>

#define SELECT_MAGIC 0x564C5345u /* "VLSE" */
#ifdef BOARD_SELECT_ADDR
#define SEL ((volatile uint32_t *)BOARD_SELECT_ADDR)
#else
extern volatile uint32_t vl_select[4];
#define SEL vl_select
#define VL_SELECT_DEFINE \
    __attribute__((section(".select"))) volatile uint32_t vl_select[4];
#endif
#ifndef VL_SELECT_DEFINE
#define VL_SELECT_DEFINE
#endif
