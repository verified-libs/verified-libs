/* Minimal TinyUSB configuration for using tu_fifo on its own (no USB stack):
 * no MCU-specific code and no RTOS. With OPT_OS_NONE TinyUSB needs no mutex
 * (OSAL_MUTEX_REQUIRED 0), which is how tu_fifo runs between a USB interrupt
 * and the main loop on bare metal. A TinyUSB application provides this file
 * itself; this one only selects those two options. */
#ifndef TUSB_CONFIG_H_
#define TUSB_CONFIG_H_
#define CFG_TUSB_MCU OPT_MCU_NONE
#define CFG_TUSB_OS  OPT_OS_NONE
#endif
