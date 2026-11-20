/* The serial-port protocol of the stress firmwares (one library per reset,
 * run parameters per run, results over the serial port; the host side is
 * common/uart_host.py). Moved here unchanged from nrf5340-rb-stress/main.c
 * on 2026-11-17, so rb-mp-stress speaks the same protocol.
 *
 * The firmware, before including this (only with HAVE_UART, i.e. a board
 * with board_uart.h):
 *   NPRM, uint32_t prm[NPRM], prm_names[NPRM], int prm_valid(void)
 *              its run parameters (the "go" line)
 *   VLS_RESULTS  its result block (sent by "dump")
 *   VLS_NSEL   the number of libraries the firmware runs; their selection
 *              indices are VLS_SEL_BASE .. VLS_SEL_BASE + VLS_NSEL - 1 (the
 *              index in a bundle, ../common/bundle.py --index-base), and
 *              "reset" selects VLS_SEL_BASE + VLS_NSEL (none of them: the
 *              firmware's own default)
 *   VLS_SEL_BASE  (default 0) first selection index of this firmware
 *   VLS_SEL_LIMIT (default VLS_SEL_BASE + VLS_NSEL) "run <n>" takes
 *              n < VLS_SEL_LIMIT: a higher limit lets the firmware select a
 *              library of another firmware in the same bundle
 *   VLS_ECC_WRITE(), VLS_ECC_READ()  writes and reads of its result block
 *              after the selection words, against the STM32H7's RAM ECC
 *              write buffer (select_and_reset)
 *   VLS_DUMP2  optional: a function sending a second block with
 *              uart_dump_block on "dump2" (rb-mp-stress COVERAGE builds:
 *              the coverage table)
 * and common/select.h (SEL). Lines from the firmware start with "VLS ". */
#pragma once
#ifndef VLS_SEL_BASE
#define VLS_SEL_BASE 0u
#endif
#ifndef VLS_SEL_LIMIT
#define VLS_SEL_LIMIT (VLS_SEL_BASE + VLS_NSEL)
#endif
static void uart_puts(const char *s) { while (*s) uart_putc(*s++); }
static void uart_putu(uint32_t v)
{
    char b[11]; int n = 0;
    do { b[n++] = (char)('0' + v % 10u); v /= 10u; } while (v);
    while (n) uart_putc(b[--n]);
}
static void uart_puthex(uint32_t v)
{
    for (int i = 28; i >= 0; i -= 4) uart_putc("0123456789abcdef"[(v >> i) & 15u]);
}
/* "dump": the whole result block, the same words the host would read over
 * the debug port: "VLS words N", N words in hex, eight per line, then
 * "VLS crc C", the CRC-32 (zlib's) of the words as little-endian bytes. Only
 * after a run (the serial port is silent while a library runs). */
static void uart_dump(void)
{
    const volatile uint32_t *w = (const volatile uint32_t *)&VLS_RESULTS;
    const uint32_t n = sizeof VLS_RESULTS / 4u;
    uint32_t crc = 0xFFFFFFFFu;
    uart_puts("VLS words ");
    uart_putu(n);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t v = w[i];
        uart_putc(i % 8u ? ' ' : '\n');
        uart_puthex(v);
        for (uint32_t k = 0; k < 32u; k++) {
            crc ^= (v >> k) & 1u;
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    uart_puts("\nVLS crc ");
    uart_puthex(~crc);
    uart_putc('\n');
}
#ifdef VLS_DUMP2
/* The same for another block, w[0..n) (VLS_DUMP2); a copy, so that the
 * images without VLS_DUMP2 stay as they were. */
static void uart_dump_block(const volatile uint32_t *w, uint32_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    uart_puts("VLS words ");
    uart_putu(n);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t v = w[i];
        uart_putc(i % 8u ? ' ' : '\n');
        uart_puthex(v);
        for (uint32_t k = 0; k < 32u; k++) {
            crc ^= (v >> k) & 1u;
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    uart_puts("\nVLS crc ");
    uart_puthex(~crc);
    uart_putc('\n');
}
static void VLS_DUMP2(void);
#endif
/* Select library l for the next start and reset (common/select.h). */
static void select_and_reset(uint32_t l)
{
    SEL[0] = SELECT_MAGIC;
    SEL[1] = l;
    SEL[2] = ~l;
    /* push the selection out of the H7's RAM ECC write buffers (DTCM is two
     * interleaved banks): the pad word after it, then one more write in each
     * bank elsewhere (VLS_ECC_WRITE, the firmware's: e.g. words at offset 8
     * and size - 4 of its result block, which are in different banks), then
     * read everything back (VLS_ECC_READ) */
#ifndef BOARD_SELECT_ADDR
    SEL[3] = 0;
#endif
    VLS_ECC_WRITE();
    (void)SEL[0]; (void)SEL[1]; (void)SEL[2];
    VLS_ECC_READ();
    uart_flush();
    __asm volatile ("dsb" ::: "memory");
    *(volatile uint32_t *)0xE000ED0Cu = 0x05FA0004u;   /* AIRCR: SYSRESETREQ */
    for (;;) {}
}
/* One line from the serial port into line[size] (NUL-terminated, cut at
 * size - 1). wait: polls to wait for it (0: for ever). Returns the length,
 * or -1 if no complete line came in time. */
static int uart_getline(char *line, uint32_t size, uint32_t wait)
{
    uint32_t n = 0, polls = 0;
    for (;;) {
        int c = uart_getc();
        if (c < 0) {
            if (wait && ++polls >= wait) return -1;
            continue;
        }
        if (c < 0x20 && c != '\n' && c != '\r') continue;   /* e.g. a NUL from a line glitch at reset */
        if (c != '\n' && c != '\r') { if (n < size - 1u) line[n++] = (char)c; continue; }
        line[n] = 0;
        return (int)n;
    }
}
/* A number, decimal or 0x hexadecimal, from s[0..len); 0 if it is not one
 * or does not fit in 32 bits. */
static int parse_u32(const char *s, uint32_t len, uint32_t *out)
{
    uint32_t base = 10u, v = 0;
    if (len > 2u && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) { base = 16u; s += 2; len -= 2u; }
    if (len == 0) return 0;
    for (uint32_t i = 0; i < len; i++) {
        char c = s[i];
        uint32_t d = (c >= '0' && c <= '9') ? (uint32_t)(c - '0')
                   : (base == 16u && c >= 'a' && c <= 'f') ? (uint32_t)(c - 'a' + 10)
                   : (base == 16u && c >= 'A' && c <= 'F') ? (uint32_t)(c - 'A' + 10) : 99u;
        if (d >= base || v > (0xFFFFFFFFu - d) / base) return 0;
        v = v * base + d;
    }
    *out = v;
    return 1;
}
/* "go name=value ...": the run parameters (prm_names) for this start; the
 * ones not named keep the build's defaults. 0 if the line is not valid. */
static int go_parse(const char *line, uint32_t n)
{
    uint32_t i = 2;
    while (i < n) {
        while (i < n && line[i] == ' ') i++;
        if (i >= n) break;
        uint32_t k0 = i;
        while (i < n && line[i] != '=' && line[i] != ' ') i++;
        if (i >= n || line[i] != '=') return 0;
        uint32_t klen = i - k0, v0 = ++i;
        while (i < n && line[i] != ' ') i++;
        uint32_t k;
        for (k = 0; k < NPRM; k++) {
            const char *name = prm_names[k];
            uint32_t j = 0;
            while (j < klen && name[j] && name[j] == line[k0 + j]) j++;
            if (j == klen && !name[j]) break;
        }
        if (k == NPRM || !parse_u32(line + v0, i - v0, &prm[k])) return 0;
    }
    return prm_valid();
}
/* After a selected reset: wait up to `wait` polls for "go ..." (go_parse;
 * empty lines are skipped). Answers "VLS go" with every parameter
 * (name=0x%08x, the order of prm_names) and returns 1, or, for any other
 * line or a bad value, "VLS error bad params" and returns 0 (the library is
 * not run). Without a line in time the build's defaults apply (also
 * answered with "VLS go"). */
static int uart_go(uint32_t wait)
{
    char line[160];
    int n;
    do n = uart_getline(line, sizeof line, wait); while (n == 0);
    if (n > 0 && !(n >= 2 && line[0] == 'g' && line[1] == 'o' && (n == 2 || line[2] == ' ')
                   && go_parse(line, (uint32_t)n))) {
        uart_puts("VLS error bad params\n");
        return 0;
    }
    uart_puts("VLS go");
    for (uint32_t k = 0; k < NPRM; k++) {
        uart_putc(' ');
        uart_puts(prm_names[k]);
        uart_puts("=0x");
        uart_puthex(prm[k]);
    }
    uart_putc('\n');
    return 1;
}
/* Commands, one per line: "run <n>" (library n, from a fresh reset; then
 * "go ..." after "VLS start <n>", see uart_go), "reset", "dump" (the result
 * block, see uart_dump), "dump2" (VLS_DUMP2, if the firmware has one).
 * wait: polls to wait (0: for ever). Returns if none came. */
static void uart_commands(uint32_t wait)
{
    char line[24];
    for (;;) {
        int r = uart_getline(line, sizeof line, wait);
        if (r < 0) return;
        uint32_t n = (uint32_t)r;
        if (n > 4 && line[0] == 'r' && line[1] == 'u' && line[2] == 'n' && line[3] == ' ') {
            uint32_t v = 0; int ok = 1;
            for (uint32_t i = 4; i < n; i++) {
                if (line[i] < '0' || line[i] > '9') { ok = 0; break; }
                v = v * 10u + (uint32_t)(line[i] - '0');
            }
            if (ok && v < VLS_SEL_LIMIT) select_and_reset(v);
            uart_puts("VLS error bad library\n");
        } else if (n == 5 && line[0] == 'r' && line[1] == 'e' && line[2] == 's') {
            select_and_reset(VLS_SEL_BASE + VLS_NSEL);   /* none of this firmware's: all libraries */
        } else if (n == 4 && line[0] == 'd' && line[1] == 'u' && line[2] == 'm' && line[3] == 'p') {
            uart_dump();
#ifdef VLS_DUMP2
        } else if (n == 5 && line[0] == 'd' && line[1] == 'u' && line[2] == 'm' && line[3] == 'p' && line[4] == '2') {
            VLS_DUMP2();
#endif
        } else if (n) {
            uart_puts("VLS error unknown command\n");
        }
    }
}
