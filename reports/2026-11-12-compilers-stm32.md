# Four compilers on the STM32 boards (2026-11-12)

The libraries under test and their adapters built with four compilers, on
the three STM32 boards (G474, H723, G0B1); harness, startup and link stay
the Debian arm-none-eabi-gcc 14.2.1 with newlib-nano in every case
(`firmware/common/compiler.mk`):

| `COMPILER=` | Compiler |
|---|---|
| `gcc` | Arm GNU Toolchain 14.2.1 (Debian `gcc-arm-none-eabi` 14.2.rel1) |
| `clang` | Ubuntu clang 21.1.8, GNU headers |
| `st-gcc` | GNU Tools for STM32 14.3.1 (STM32CubeCLT 1.22.0) |
| `st-clang` | ST Arm Clang 21.1.1 (`starm-clang`, CubeCLT 1.22.0), GNU headers |

The ST compilers run from a local image that is never pushed (ST licence
SLA0048; [toolchain/st](../toolchain/st/README.md)), and only for STM32
boards (its clause 4).

## Correctness
ISR stress (single bytes, blocks, DMA zero-copy) with `st-gcc` and
`st-clang` at `-O2` (18 runs) and with `st-clang-omax` at `-O3` (9 runs):
all valid (control caught), **0 errors in every real library**. Records:
`~/lab-runs/st-compilers-20261112/<board>/` and
`~/lab-runs/st-omax-20261112/<board>/`.

## Same code, mostly
Object code compared function by function (`objdump -d`, addresses
stripped), 44 objects per build:

| Pair | G474 (M4) | G0B1 (M0+) |
|---|---|---|
| `st-clang` vs `clang` | 0 differ | 0 differ |
| `st-gcc` vs `gcc` | 11 differ | 2 differ |
| `clang` vs `gcc` | 40 differ | 40 differ |

- ST Arm Clang 21.1.1 and Ubuntu clang 21.1.8 generate byte-identical code
  for these libraries with the same flags and headers. What ST adds is its
  runtime (newlib, libc++; not used here) and its optimisation presets
  (below).
- GNU Tools for STM32 14.3.1 differs from Arm GCC 14.2.1 in small ways
  (operand order of a compare, register choice). In the bench the cycles are
  the same in every cell on the G474 and G0B1; on the H723 two cells differ
  (lwrb push 151 vs 145, micoring single-context block 30.7 vs 29.0
  cycles/byte).

So, for these libraries, "ST's compiler" measures the same as the
upstream compiler of the same family; the gcc/clang choice is what matters.

## gcc vs clang (`-O2`, flash, cache on)
Sum of mean push + pop cycles (1 byte) over the 29 library builds:

| Board | gcc / st-gcc | clang / st-clang | clang vs gcc |
|---|---|---|---|
| G474 (M4) | 3 848 | 3 980 | +3 % |
| H723 (M7) | 3 038 (st-gcc 3 044) | 2 931 | −4 % |
| G0B1 (M0+) | 5 610 | 6 952 | +24 % |

On the M4 and M7 the two trade places library by library (clang is faster
for lockfree spsc::RingBuf, FreeRTOS stream buffer, diffstorm; gcc for lwrb,
Zephyr ring_buf, polycratia). On the M0+ clang is much slower for every
library that uses C11/C++11 atomics: clang lowers each atomic load and
store on ARMv6-M to a call to `__atomic_load_N` / `__atomic_store_N` (gcc
inlines LDR/STR with DMB). Here those calls go to
`firmware/common/armv6m_atomic.c`, which does what gcc inlines, after a
switch on the memory order. Examples (push/pop cycles, gcc → clang): jnk0le
36/42 → 113/118, ETL queue_spsc_atomic 54/51 → 121/121, QuantumLeaps LFRB
69/61 → 174/154, rt-spsc 45/44 → 122/118, polycratia 39/46 → 124/129.
Libraries without atomics (lwrb, ece-mohammad, TinyUSB, the
interrupt-masking designs) are within a few cycles. A program built with
clang for an M0+ has to supply these functions somehow; how cheaply it does
so decides the cost of every atomic access.

All cells are in the appendix.

## ST's Omax preset (`COMPILER=st-clang-omax`, `-O3`)
`starm-clang --config=Omax.cfg`, ST's speed preset shipped with the compiler: `-O3` plus LLVM
options for more inlining and unrolling, loop flattening, unroll-and-jam,
DFA jump threading and inlined memcpy loads/stores. Compared with gcc and
clang at `-O3` (same harness flags). It changes 9 of the 44 objects against
clang `-O3`. Sum of mean push + pop cycles over the 29 library builds:

| Board | gcc `-O3` | clang `-O3` | st-clang Omax | Omax vs clang `-O3` | Omax vs gcc `-O3` |
|---|---|---|---|---|---|
| G474 (M4) | 3 468 | 3 916 | 3 672 | −6 % | +6 % |
| H723 (M7) | 2 731 | 2 981 | 2 866 | −4 % | +5 % |
| G0B1 (M0+) | 5 101 | 6 896 | 6 780 | −2 % | +33 % |

Almost all of the gain is in the two libraries that call `memcpy` in their
single-byte path, lwrb and the FreeRTOS stream buffer, which fits the
preset's inlined memcpy (not checked instruction by instruction) (G474 lwrb
push/pop: clang `-O3` 222/212, Omax 138/133, gcc `-O3` 129/125); the other
libraries measure the same as clang `-O3`. gcc at `-O3` is the fastest of
the three on every board.

## Appendix: all cells, `-O2`

Cells: push / pop mean cycles (1 byte) · 64-byte block, cycles per byte (mean of push and pop); flash, cache on.

### NUCLEO-G474RE

| Library | gcc | clang | st-gcc | st-clang |
|---|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 20/21 · 7.5 | 22/24 · 5.9 | 20/21 · 7.5 | 22/24 · 5.9 |
| lwrb (C) | 180/176 · 5.1 | 210/208 · 5.0 | 180/176 · 5.1 | 210/208 · 5.0 |
| AndersKaloer Ring-Buffer (C) | 57/41 · 20.1 | 68/41 · 20.8 | 57/41 · 20.1 | 68/41 · 20.8 |
| jnk0le Ringbuffer (C++) | 23/26 · 9.5 | 27/36 · 8.8 | 23/26 · 9.5 | 27/36 · 8.8 |
| ETL queue_spsc_isr (C++) | 40/45 · 31.9 | 44/45 · 28.9 | 40/45 · 31.9 | 44/45 · 28.9 |
| ETL queue_spsc_atomic (C++) | 30/27 · 23.9 | 37/38 · 22.4 | 30/27 · 23.9 | 37/38 · 22.4 |
| QuantumLeaps LFRB (C) | 46/46 · 53.4 | 56/54 · 60.9 | 46/46 · 53.4 | 56/54 · 60.9 |
| EmbeddedArtistry cbuf threadsafe (C) | 56/46 · 58.4 | 61/50 · 60.9 | 56/46 · 58.4 | 61/50 · 60.9 |
| ece-mohammad RingBuffer (C) | 81/80 · 4.2 | 87/81 · 4.2 | 81/80 · 4.2 | 87/81 · 4.2 |
| micoring SPSC mode (C) | 98/97 · 96.9 | 107/101 · 71.4 | 98/97 · 96.9 | 107/101 · 71.4 |
| kostyk348 lf_spsc (C) | 72/67 · 79.4 | 82/68 · 81.4 | 72/67 · 79.4 | 82/68 · 81.4 |
| diffstorm cb (C) | 72/69 · 77.9 | 56/59 · 62.9 | 72/69 · 77.9 | 56/59 · 62.9 |
| RIOT tsrb (C) | 52/51 · 19.6 | 55/55 · 21.0 | 52/51 · 19.6 | 55/55 · 21.0 |
| Contiki-NG ringbuf (C) | 45/42 · 51.9 | 44/41 · 49.4 | 45/42 · 51.9 | 44/41 · 49.4 |
| rigtorp SPSCQueue (C++) | 35/49 · 45.5 | 37/38 · 39.9 | 35/49 · 45.5 | 37/38 · 39.9 |
| wizard97 as shipped (C++) | 29/25 · 33.4 | 29/28 · 32.4 | 29/25 · 33.4 | 29/28 · 32.4 |
| wizard97 + PRIMASK macros (C++) | 40/32 · 43.9 | 36/31 · 38.4 | 40/32 · 43.9 | 36/31 · 38.4 |
| polycratia spscring (C++) | 24/28 · 9.5 | 38/31 · 8.5 | 24/28 · 9.5 | 38/31 · 8.5 |
| rt-spsc (C++) | 26/24 · 31.9 | 26/26 · 30.4 | 26/24 · 31.9 | 26/26 · 30.4 |
| TinyUSB tu_fifo (C) | 101/100 · 4.2 | 105/103 · 4.5 | 101/100 · 4.2 | 105/103 · 4.5 |
| Zephyr ring_buf (C) | 79/74 · 3.7 | 94/89 · 4.0 | 79/74 · 3.7 | 94/89 · 4.0 |
| Zephyr ring_buf, CONFIG_SMP (C) | 86/83 · 4.0 | 96/91 · 4.1 | 86/83 · 4.0 | 96/91 · 4.1 |
| DNedic lockfree spsc::RingBuf (C++) | 98/88 · 3.8 | 58/49 · 3.3 | 98/88 · 3.8 | 58/49 · 3.3 |
| ETL queue_spsc_locked (C++) | 79/80 · 61.5 | 83/82 · 58.0 | 79/80 · 61.5 | 83/82 · 58.0 |
| FreeRTOS stream buffer (C) | 355/273 · 6.7 | 318/274 · 6.3 | 355/273 · 6.7 | 318/274 · 6.3 |
| pxq Topology::None, single-context (C++) | 19/20 · 7.5 | 21/24 · 5.9 | 19/20 · 7.5 | 21/24 · 5.9 |
| micoring default, single-context (C) | 78/75 · 66.5 | 84/77 · 60.0 | 78/75 · 66.5 | 84/77 · 60.0 |
| EmbeddedArtistry cbuf basic, single-context (C) | 40/36 · 43.9 | 50/40 · 49.4 | 40/36 · 43.9 | 50/40 · 49.4 |
| ETL etl::queue, single-context (C++) | 32/34 · 38.9 | 32/33 · 36.4 | 32/34 · 38.9 | 32/33 · 36.4 |
| **sum push+pop (single)** | 3848 (29) | 3980 (29) | 3848 (29) | 3980 (29) |

Records: gcc `stm32g474-rb-bench-flash-20261112T125732Z.json`, clang `stm32g474-rb-bench-flash-clang-20261112T125853Z.json`, st-gcc `stm32g474-rb-bench-flash-st-gcc-20261112T103459Z.json`, st-clang `stm32g474-rb-bench-flash-st-clang-20261112T104846Z.json`.

### NUCLEO-H723ZG

| Library | gcc | clang | st-gcc | st-clang |
|---|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 17/16 · 3.5 | 17/19 · 3.3 | 17/16 · 3.5 | 17/19 · 3.3 |
| lwrb (C) | 145/136 · 3.8 | 96/94 · 3.7 | 151/136 · 3.9 | 96/94 · 3.7 |
| AndersKaloer Ring-Buffer (C) | 33/26 · 9.2 | 35/27 · 9.7 | 33/26 · 9.2 | 35/27 · 9.7 |
| jnk0le Ringbuffer (C++) | 35/35 · 6.6 | 36/36 · 3.8 | 35/35 · 6.6 | 36/36 · 3.8 |
| ETL queue_spsc_isr (C++) | 42/45 · 28.5 | 45/46 · 26.4 | 42/45 · 28.5 | 45/46 · 26.4 |
| ETL queue_spsc_atomic (C++) | 38/37 · 26.1 | 41/40 · 27.4 | 38/37 · 26.1 | 41/40 · 27.4 |
| QuantumLeaps LFRB (C) | 46/41 · 35.7 | 51/43 · 37.4 | 46/41 · 35.7 | 51/43 · 37.4 |
| EmbeddedArtistry cbuf threadsafe (C) | 37/31 · 25.4 | 37/33 · 25.4 | 37/31 · 25.4 | 37/33 · 25.4 |
| ece-mohammad RingBuffer (C) | 51/50 · 3.0 | 53/49 · 3.2 | 51/50 · 3.0 | 53/49 · 3.2 |
| micoring SPSC mode (C) | 72/72 · 59.9 | 79/71 · 48.4 | 72/72 · 59.9 | 79/71 · 48.4 |
| kostyk348 lf_spsc (C) | 64/59 · 56.2 | 67/57 · 51.4 | 64/59 · 56.2 | 67/57 · 51.4 |
| diffstorm cb (C) | 50/63 · 48.4 | 44/57 · 40.5 | 50/63 · 48.4 | 44/57 · 40.5 |
| RIOT tsrb (C) | 46/45 · 11.4 | 44/41 · 11.2 | 46/45 · 11.4 | 44/41 · 11.2 |
| Contiki-NG ringbuf (C) | 32/28 · 22.2 | 34/30 · 21.9 | 32/28 · 22.2 | 34/30 · 21.9 |
| rigtorp SPSCQueue (C++) | 37/43 · 29.1 | 37/39 · 26.6 | 37/43 · 29.1 | 37/39 · 26.6 |
| wizard97 as shipped (C++) | 24/22 · 16.5 | 25/24 · 17.9 | 24/22 · 16.5 | 25/24 · 17.9 |
| wizard97 + PRIMASK macros (C++) | 52/49 · 43.9 | 53/49 · 44.4 | 52/49 · 43.9 | 53/49 · 44.4 |
| polycratia spscring (C++) | 38/32 · 5.2 | 42/35 · 3.8 | 38/32 · 5.2 | 42/35 · 3.8 |
| rt-spsc (C++) | 36/36 · 28.9 | 36/36 · 29.9 | 36/36 · 28.9 | 36/36 · 29.9 |
| TinyUSB tu_fifo (C) | 61/64 · 3.5 | 68/68 · 3.4 | 61/64 · 3.5 | 68/68 · 3.4 |
| Zephyr ring_buf (C) | 53/51 · 3.0 | 68/64 · 3.3 | 53/51 · 3.0 | 68/64 · 3.3 |
| Zephyr ring_buf, CONFIG_SMP (C) | 71/66 · 3.3 | 77/71 · 3.4 | 71/66 · 3.3 | 77/71 · 3.4 |
| DNedic lockfree spsc::RingBuf (C++) | 68/65 · 3.2 | 52/48 · 3.2 | 68/65 · 3.2 | 52/48 · 3.2 |
| ETL queue_spsc_locked (C++) | 69/68 · 43.6 | 74/73 · 43.6 | 69/68 · 43.6 | 74/73 · 43.6 |
| FreeRTOS stream buffer (C) | 214/161 · 4.6 | 165/125 · 4.1 | 214/161 · 4.6 | 165/125 · 4.1 |
| pxq Topology::None, single-context (C++) | 24/21 · 3.8 | 22/26 · 3.3 | 24/21 · 3.8 | 22/26 · 3.3 |
| micoring default, single-context (C) | 50/54 · 29.0 | 61/53 · 36.5 | 50/54 · 30.7 | 61/53 · 36.5 |
| EmbeddedArtistry cbuf basic, single-context (C) | 33/30 · 24.9 | 39/31 · 27.4 | 33/30 · 24.9 | 39/31 · 27.4 |
| ETL etl::queue, single-context (C++) | 25/26 · 19.4 | 23/23 · 16.5 | 25/26 · 19.4 | 23/23 · 16.5 |
| **sum push+pop (single)** | 3038 (29) | 2931 (29) | 3044 (29) | 2931 (29) |

Records: gcc `stm32h723-rb-bench-flash-20261112T125734Z.json`, clang `stm32h723-rb-bench-flash-clang-20261112T125855Z.json`, st-gcc `stm32h723-rb-bench-flash-st-gcc-20261112T103502Z.json`, st-clang `stm32h723-rb-bench-flash-st-clang-20261112T105426Z.json`.

### NUCLEO-G0B1RE

| Library | gcc | clang | st-gcc | st-clang |
|---|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 35/38 · 10.2 | 35/37 · 7.4 | 35/38 · 10.2 | 35/37 · 7.4 |
| lwrb (C) | 263/256 · 13.5 | 305/299 · 14.1 | 263/256 · 13.5 | 305/299 · 14.1 |
| AndersKaloer Ring-Buffer (C) | 73/50 · 27.3 | 82/51 · 26.4 | 73/50 · 27.3 | 82/51 · 26.4 |
| jnk0le Ringbuffer (C++) | 36/42 · 11.8 | 113/118 · 12.5 | 36/42 · 11.8 | 113/118 · 12.5 |
| ETL queue_spsc_isr (C++) | 73/68 · 53.6 | 59/58 · 40.5 | 73/68 · 53.6 | 59/58 · 40.5 |
| ETL queue_spsc_atomic (C++) | 54/51 · 40.0 | 121/121 · 98.1 | 54/51 · 40.0 | 121/121 · 98.1 |
| QuantumLeaps LFRB (C) | 69/61 · 79.9 | 174/154 · 175.8 | 69/61 · 79.9 | 174/154 · 175.8 |
| EmbeddedArtistry cbuf threadsafe (C) | 74/60 · 81.9 | 79/65 · 83.8 | 74/60 · 81.9 | 79/65 · 83.8 |
| ece-mohammad RingBuffer (C) | 111/109 · 12.4 | 112/109 · 12.1 | 111/109 · 12.4 | 112/109 · 12.1 |
| micoring SPSC mode (C) | 127/131 · 128.2 | 182/179 · 154.6 | 127/131 · 128.2 | 182/179 · 154.6 |
| kostyk348 lf_spsc (C) | 159/154 · 212.6 | 179/166 · 184.3 | 159/154 · 212.6 | 179/166 · 184.3 |
| diffstorm cb (C) | 122/131 · 141.4 | 186/182 · 195.8 | 122/131 · 141.4 | 186/182 · 195.8 |
| RIOT tsrb (C) | 65/64 · 30.1 | 72/62 · 25.4 | 65/64 · 30.1 | 72/62 · 25.4 |
| Contiki-NG ringbuf (C) | 61/53 · 71.9 | 63/52 · 69.3 | 61/53 · 71.9 | 63/52 · 69.3 |
| rigtorp SPSCQueue (C++) | 52/83 · 73.2 | 109/178 · 141.7 | 52/83 · 73.2 | 109/178 · 141.7 |
| wizard97 as shipped (C++) | 41/41 · 55.9 | 48/47 · 59.3 | 41/41 · 55.9 | 48/47 · 59.3 |
| wizard97 + PRIMASK macros (C++) | 57/61 · 73.9 | 63/58 · 72.3 | 57/61 · 73.9 | 63/58 · 72.3 |
| polycratia spscring (C++) | 39/46 · 11.8 | 124/129 · 11.9 | 39/46 · 11.8 | 124/129 · 11.9 |
| rt-spsc (C++) | 45/44 · 59.4 | 122/118 · 131.8 | 45/44 · 59.4 | 122/118 · 131.8 |
| TinyUSB tu_fifo (C) | 138/131 · 12.3 | 133/134 · 12.3 | 138/131 · 12.3 | 133/134 · 12.3 |
| Zephyr ring_buf (C) | 115/105 · 10.4 | 126/127 · 11.2 | 115/105 · 10.4 | 126/127 · 11.2 |
| Zephyr ring_buf, CONFIG_SMP (C) | 129/117 · 11.0 | 227/225 · 13.0 | 129/117 · 11.0 | 227/225 · 13.0 |
| DNedic lockfree spsc::RingBuf (C++) | 163/155 · 12.3 | 135/135 · 13.6 | 163/155 · 12.3 | 135/135 · 13.6 |
| ETL queue_spsc_locked (C++) | 115/110 · 92.5 | 109/101 · 85.6 | 115/110 · 92.5 | 109/101 · 85.6 |
| FreeRTOS stream buffer (C) | 373/325 · 13.1 | 300/249 · 11.8 | 373/325 · 13.1 | 300/249 · 11.8 |
| pxq Topology::None, single-context (C++) | 35/38 · 10.2 | 35/37 · 7.4 | 35/38 · 10.2 | 35/37 · 7.4 |
| micoring default, single-context (C) | 103/98 · 90.9 | 106/100 · 93.3 | 103/98 · 90.9 | 106/100 · 93.3 |
| EmbeddedArtistry cbuf basic, single-context (C) | 87/80 · 98.4 | 97/81 · 100.8 | 87/80 · 98.4 | 97/81 · 100.8 |
| ETL etl::queue, single-context (C++) | 46/47 · 61.4 | 43/41 · 53.9 | 46/47 · 61.4 | 43/41 · 53.9 |
| **sum push+pop (single)** | 5610 (29) | 6952 (29) | 5610 (29) | 6952 (29) |

Records: gcc `stm32g0b1-rb-bench-flash-20261112T125733Z.json`, clang `stm32g0b1-rb-bench-flash-clang-20261112T125853Z.json`, st-gcc `stm32g0b1-rb-bench-flash-st-gcc-20261112T104719Z.json`, st-clang `stm32g0b1-rb-bench-flash-st-clang-20261112T112322Z.json`.

## Appendix: all cells, `-O3`

### NUCLEO-G474RE

| Library | gcc -O3 | clang -O3 | Omax |
|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 20/21 · 7.5 | 22/24 · 6.3 | 22/24 · 6.8 |
| lwrb (C) | 129/125 · 4.0 | 222/212 · 5.1 | 138/133 · 4.3 |
| AndersKaloer Ring-Buffer (C) | 57/41 · 19.6 | 68/41 · 20.8 | 68/41 · 20.8 |
| jnk0le Ringbuffer (C++) | 23/26 · 9.5 | 27/36 · 8.8 | 27/36 · 9.0 |
| ETL queue_spsc_isr (C++) | 40/45 · 32.5 | 44/45 · 28.9 | 44/45 · 28.9 |
| ETL queue_spsc_atomic (C++) | 30/27 · 25.4 | 37/38 · 22.4 | 37/38 · 22.4 |
| QuantumLeaps LFRB (C) | 46/46 · 52.4 | 56/54 · 60.9 | 56/54 · 60.9 |
| EmbeddedArtistry cbuf threadsafe (C) | 56/46 · 57.4 | 61/50 · 60.9 | 61/50 · 60.9 |
| ece-mohammad RingBuffer (C) | 81/80 · 4.4 | 87/81 · 4.4 | 87/81 · 4.4 |
| micoring SPSC mode (C) | 98/97 · 70.0 | 107/101 · 70.3 | 107/101 · 70.3 |
| kostyk348 lf_spsc (C) | 72/67 · 78.4 | 73/62 · 73.9 | 73/62 · 73.9 |
| diffstorm cb (C) | 54/52 · 59.4 | 56/58 · 62.4 | 56/58 · 62.4 |
| RIOT tsrb (C) | 52/51 · 19.6 | 55/54 · 21.0 | 55/54 · 21.0 |
| Contiki-NG ringbuf (C) | 45/42 · 50.9 | 44/41 · 49.4 | 44/41 · 49.4 |
| rigtorp SPSCQueue (C++) | 35/49 · 44.5 | 37/38 · 39.9 | 37/38 · 39.9 |
| wizard97 as shipped (C++) | 29/27 · 34.9 | 29/28 · 32.4 | 29/28 · 32.4 |
| wizard97 + PRIMASK macros (C++) | 40/32 · 43.9 | 36/31 · 38.4 | 36/31 · 38.4 |
| polycratia spscring (C++) | 24/28 · 9.5 | 38/31 · 8.5 | 38/31 · 8.5 |
| rt-spsc (C++) | 26/24 · 30.9 | 26/26 · 30.4 | 26/26 · 30.4 |
| TinyUSB tu_fifo (C) | 101/100 · 4.2 | 105/103 · 4.4 | 105/103 · 4.4 |
| Zephyr ring_buf (C) | 79/74 · 4.0 | 85/79 · 3.5 | 85/79 · 3.5 |
| Zephyr ring_buf, CONFIG_SMP (C) | 86/83 · 4.2 | 88/82 · 3.6 | 88/82 · 3.6 |
| DNedic lockfree spsc::RingBuf (C++) | 55/48 · 3.9 | 57/50 · 3.4 | 57/50 · 3.4 |
| ETL queue_spsc_locked (C++) | 79/80 · 59.6 | 83/82 · 58.0 | 83/82 · 58.0 |
| FreeRTOS stream buffer (C) | 257/209 · 5.4 | 301/264 · 6.1 | 266/217 · 5.3 |
| pxq Topology::None, single-context (C++) | 19/20 · 7.5 | 21/24 · 6.3 | 21/24 · 6.7 |
| micoring default, single-context (C) | 78/75 · 57.4 | 84/77 · 62.5 | 84/77 · 58.0 |
| EmbeddedArtistry cbuf basic, single-context (C) | 40/36 · 43.9 | 50/40 · 49.4 | 50/40 · 49.4 |
| ETL etl::queue, single-context (C++) | 32/34 · 38.9 | 32/33 · 36.4 | 32/33 · 36.4 |
| **sum push+pop (single)** | 3468 (29) | 3916 (29) | 3672 (29) |

Records: gcc -O3 `stm32g474-rb-bench-flash-O3-20261112T130534Z.json`, clang -O3 `stm32g474-rb-bench-flash-O3-clang-20261112T130654Z.json`, Omax `stm32g474-rb-bench-flash-O3-st-clang-omax-20261112T130813Z.json`.

### NUCLEO-H723ZG

| Library | gcc -O3 | clang -O3 | Omax |
|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 17/16 · 3.5 | 17/19 · 3.4 | 17/19 · 3.5 |
| lwrb (C) | 100/90 · 3.2 | 107/105 · 3.7 | 91/90 · 3.6 |
| AndersKaloer Ring-Buffer (C) | 33/26 · 10.0 | 35/27 · 9.7 | 35/27 · 9.7 |
| jnk0le Ringbuffer (C++) | 35/35 · 6.6 | 36/36 · 3.7 | 36/36 · 3.9 |
| ETL queue_spsc_isr (C++) | 42/45 · 27.5 | 45/47 · 26.4 | 45/47 · 26.4 |
| ETL queue_spsc_atomic (C++) | 38/37 · 26.7 | 42/42 · 27.4 | 42/42 · 27.4 |
| QuantumLeaps LFRB (C) | 46/41 · 34.9 | 52/43 · 37.5 | 52/43 · 37.5 |
| EmbeddedArtistry cbuf threadsafe (C) | 37/31 · 25.4 | 38/33 · 25.4 | 38/33 · 25.4 |
| ece-mohammad RingBuffer (C) | 51/51 · 3.2 | 55/51 · 3.2 | 55/51 · 3.2 |
| micoring SPSC mode (C) | 72/72 · 49.2 | 74/74 · 47.5 | 74/74 · 47.5 |
| kostyk348 lf_spsc (C) | 65/60 · 56.2 | 66/55 · 50.0 | 66/55 · 50.0 |
| diffstorm cb (C) | 43/55 · 39.9 | 45/57 · 40.5 | 45/57 · 40.5 |
| RIOT tsrb (C) | 46/44 · 11.4 | 44/41 · 11.2 | 44/41 · 11.2 |
| Contiki-NG ringbuf (C) | 31/29 · 20.9 | 33/30 · 21.9 | 33/30 · 21.9 |
| rigtorp SPSCQueue (C++) | 36/42 · 28.6 | 37/39 · 26.6 | 37/39 · 26.6 |
| wizard97 as shipped (C++) | 24/22 · 16.5 | 25/24 · 17.9 | 25/24 · 17.9 |
| wizard97 + PRIMASK macros (C++) | 51/49 · 43.4 | 53/49 · 44.4 | 53/49 · 44.4 |
| polycratia spscring (C++) | 37/32 · 5.2 | 42/35 · 3.7 | 42/35 · 3.7 |
| rt-spsc (C++) | 35/36 · 28.9 | 36/36 · 29.9 | 36/36 · 29.9 |
| TinyUSB tu_fifo (C) | 61/64 · 3.4 | 69/70 · 3.5 | 69/70 · 3.5 |
| Zephyr ring_buf (C) | 53/51 · 3.1 | 64/60 · 3.1 | 64/60 · 3.1 |
| Zephyr ring_buf, CONFIG_SMP (C) | 73/66 · 3.4 | 75/70 · 3.2 | 75/70 · 3.2 |
| DNedic lockfree spsc::RingBuf (C++) | 51/48 · 3.3 | 51/48 · 3.2 | 51/48 · 3.2 |
| ETL queue_spsc_locked (C++) | 69/66 · 44.5 | 74/72 · 42.9 | 74/72 · 42.9 |
| FreeRTOS stream buffer (C) | 118/98 · 3.7 | 189/135 · 4.0 | 139/100 · 3.6 |
| pxq Topology::None, single-context (C++) | 23/21 · 3.7 | 22/26 · 3.3 | 22/26 · 3.4 |
| micoring default, single-context (C) | 49/53 · 25.8 | 61/53 · 36.5 | 61/53 · 35.5 |
| EmbeddedArtistry cbuf basic, single-context (C) | 33/29 · 24.9 | 39/31 · 27.5 | 39/32 · 27.5 |
| ETL etl::queue, single-context (C++) | 25/26 · 19.4 | 23/24 · 16.5 | 23/24 · 16.5 |
| **sum push+pop (single)** | 2731 (29) | 2981 (29) | 2866 (29) |

Records: gcc -O3 `stm32h723-rb-bench-flash-O3-20261112T130535Z.json`, clang -O3 `stm32h723-rb-bench-flash-O3-clang-20261112T130656Z.json`, Omax `stm32h723-rb-bench-flash-O3-st-clang-omax-20261112T130816Z.json`.

### NUCLEO-G0B1RE

| Library | gcc -O3 | clang -O3 | Omax |
|---|---|---|---|
| pxq RingBuffer_PackedState (C++) | 35/38 · 10.2 | 35/37 · 7.4 | 35/37 · 7.4 |
| lwrb (C) | 187/183 · 12.4 | 309/298 · 14.1 | 280/275 · 13.6 |
| AndersKaloer Ring-Buffer (C) | 73/50 · 27.3 | 82/51 · 26.4 | 82/51 · 26.4 |
| jnk0le Ringbuffer (C++) | 36/42 · 11.8 | 113/118 · 12.5 | 113/118 · 12.5 |
| ETL queue_spsc_isr (C++) | 73/68 · 51.8 | 59/58 · 40.5 | 59/58 · 40.5 |
| ETL queue_spsc_atomic (C++) | 54/51 · 39.6 | 121/121 · 98.1 | 121/121 · 98.1 |
| QuantumLeaps LFRB (C) | 69/61 · 78.9 | 174/154 · 175.8 | 174/154 · 175.8 |
| EmbeddedArtistry cbuf threadsafe (C) | 74/60 · 80.9 | 79/65 · 83.8 | 79/65 · 83.8 |
| ece-mohammad RingBuffer (C) | 111/109 · 12.4 | 112/110 · 12.2 | 112/110 · 12.2 |
| micoring SPSC mode (C) | 127/131 · 99.8 | 182/177 · 148.4 | 182/177 · 148.4 |
| kostyk348 lf_spsc (C) | 159/154 · 211.6 | 170/169 · 181.3 | 170/169 · 181.3 |
| diffstorm cb (C) | 108/109 · 122.4 | 186/181 · 195.8 | 186/181 · 195.8 |
| RIOT tsrb (C) | 65/64 · 30.1 | 72/62 · 25.4 | 72/62 · 25.4 |
| Contiki-NG ringbuf (C) | 61/53 · 70.9 | 63/52 · 69.3 | 63/52 · 69.3 |
| rigtorp SPSCQueue (C++) | 52/83 · 71.1 | 109/178 · 141.7 | 109/178 · 141.7 |
| wizard97 as shipped (C++) | 41/41 · 53.9 | 48/47 · 59.3 | 48/47 · 59.3 |
| wizard97 + PRIMASK macros (C++) | 57/61 · 73.9 | 63/58 · 72.3 | 63/58 · 72.3 |
| polycratia spscring (C++) | 39/46 · 11.8 | 124/129 · 11.9 | 124/129 · 11.9 |
| rt-spsc (C++) | 45/44 · 57.4 | 129/118 · 135.3 | 129/118 · 135.3 |
| TinyUSB tu_fifo (C) | 132/130 · 12.2 | 133/132 · 12.1 | 133/132 · 12.1 |
| Zephyr ring_buf (C) | 115/105 · 10.4 | 118/113 · 10.3 | 118/113 · 10.3 |
| Zephyr ring_buf, CONFIG_SMP (C) | 129/117 · 11.0 | 212/212 · 12.3 | 212/212 · 12.3 |
| DNedic lockfree spsc::RingBuf (C++) | 92/81 · 12.4 | 135/135 · 13.6 | 135/135 · 13.6 |
| ETL queue_spsc_locked (C++) | 115/110 · 91.4 | 109/101 · 85.6 | 109/101 · 85.6 |
| FreeRTOS stream buffer (C) | 290/237 · 11.9 | 298/244 · 11.8 | 265/213 · 11.3 |
| pxq Topology::None, single-context (C++) | 35/38 · 10.2 | 35/37 · 7.4 | 35/37 · 7.4 |
| micoring default, single-context (C) | 103/98 · 83.1 | 106/100 · 92.9 | 106/100 · 87.1 |
| EmbeddedArtistry cbuf basic, single-context (C) | 87/80 · 98.4 | 97/81 · 100.8 | 97/81 · 100.8 |
| ETL etl::queue, single-context (C++) | 46/47 · 61.4 | 43/41 · 53.9 | 43/41 · 53.9 |
| **sum push+pop (single)** | 5101 (29) | 6896 (29) | 6780 (29) |

Records: gcc -O3 `stm32g0b1-rb-bench-flash-O3-20261112T130535Z.json`, clang -O3 `stm32g0b1-rb-bench-flash-O3-clang-20261112T130654Z.json`, Omax `stm32g0b1-rb-bench-flash-O3-st-clang-omax-20261112T130813Z.json`.

## Record fix
Until this commit the run scripts wrote a fixed `toolchain_image`
(`verified-libs/toolchain:2026-11-05`) into every record, also for ST builds.
The 24 ST records of 2026-11-12 (6 bench, 18 stress) were corrected to
`verified-libs/toolchain-st:cubeclt-1.22.0` with a `toolchain_image_note`;
their `toolchain` block (from the image itself) was right all along. The
scripts now write the image they ran.
