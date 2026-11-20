# nRF5340 network core: feasibility tests for plan item 2a (2026-11-17)

Two tiny firmware pairs, built by hand (no harness), each run once on the
nRF5340 DK in the lab.

**1. The network core writes application RAM** (`net.c` + `app.c`). The
application core sets SPU EXTDOMAIN[0].PERM SECATTR (0x50003440 bit 4) and
releases the network core (RESET.NETWORK.FORCEOFF, 0x50005614 = 0; nrfx MDK
nrf5340_application.h). The network core (flash 0x01000000, RAM
0x21000000) then writes a magic word and a counter at 0x20070000, which it
sees at the application core's address. Result: it runs and writes; the
counter rises between reads.

Notes from getting there:
- The release must come from the application core's firmware: a write to
  FORCEOFF over the debug port (probe-rs `nRF5340_xxAA_APPONLY`) does not
  stay (probe-rs's session start holds the network core off).
- The network core was protected (APPROTECT); `probe-rs download --chip
  nRF5340_xxAA --allow-erase-all` unlocked it by erasing - **both cores'
  flash** (the application core's bundle had to be written again).

**2. Atomic read-modify-write across the two cores** (`atomic_net.c` +
`atomic_app.c`). Both cores add 1 to the same word in application RAM a
million times with `__atomic_fetch_add` (LDREX/STREX), and to another word
with a plain read-add-write, at the same time.

| Run | Atomic (want 2000000) | Plain |
|---|---|---|
| 1 | 1553954 | 1625400 |
| 2 | 1515613 | 1625282 |
| 3 | 1517418 | 1625256 |
| 4 | 1572657 | 1583905 |

21-24 % of the atomic increments are lost: LDREX/STREX is **not atomic
between the application and the network core** in application RAM (each
core's exclusive monitor sees only its own accesses). This is a property
of the chip, not of any library; it fits the nRF5340 having a MUTEX
peripheral for locks between its cores (to be checked against the product
specification). Consequence for 2a: libraries that rely on compare-and-swap
cannot be used across the two cores of an nRF5340; the cross-core test is
for SPSC libraries (one producer core, one consumer core) that need only
plain loads and stores with barriers.

Build (toolchain image): `arm-none-eabi-gcc -mcpu=cortex-m33 -mthumb -O2
-ffreestanding -nostdlib -T net.ld net.c -o net.elf` (network core),
`-T app.ld app.c` (application core); the same for the atomic pair.
