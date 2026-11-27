# Pools: the two checks before kind A

2026-11-24. **Reviewed 2026-11-26** (the owner's decision of 2026-11-26,
[`DECISIONS.md`](../DECISIONS.md)), against the report's own data:
- both checks were run again from the pins (`pilot/pools-prechecks/run.sh`,
  `verify/exclusive/run.sh`), and their output is the same as below, line
  for line;
- the source lines cited were read at `b566de4`: `rtx_mempool.c` 77–108,
  113–148, 154–185 and 684–732, `rtx_core_cm.h` 47–57 and 931–1001, and
  `rtx_evr.c` 302–309;
- the thirteen quotations from DDI 0403E.e and DDI0553B.z were found word
  for word in the two manuals in `~/vl-dev/datasheets`.

The decision of 2026-11-24
([next kind](2026-11-24-next-kind.md), "Review and decision") put two
checks on the host before fixed-block pools (kind A) are started: can
CMSIS-RTX's pool be built alone, and can LDREX/STREX be modelled on the
host model. If they fail, A loses its hard cases. Nothing here used a
board or wrote flash.

| Check | Answer | Rests on |
|---|---|---|
| 1. CMSIS-RTX's pool built alone | **Yes**, for the Cortex-M builds with nothing of the kernel stubbed; on the host only the pool's three functions, cut out of the file unchanged, and only its Armv6-M (interrupts-off) variant | The cross build and the host test below |
| 2. LDREX/STREX on the host model | **Yes, for one core**, with what it cannot represent listed below; its rules checked against the Arm manuals (DDI 0403E.e, DDI0553B.z), with a mode for a STREX failing without a cause | A made-up lock-free free list and its variants below |

## Check 1: CMSIS-RTX's pool without the kernel

**What was built.** CMSIS-RTX v5.9.1 (`b566de4`, Apache-2.0, from the
licence file), with the CMSIS 6 headers v6.4.0 (`af1b110`) and the device
headers of Cortex_DFP v1.2.0 (`cd38dbb`), pinned in
[`pilot/pools-prechecks/libs.lock`](../pilot/pools-prechecks/libs.lock).
The kernel's pool object (`osMemoryPoolNew`/`Alloc`/`Free`) reaches the
pool through the SVC call or, from an interrupt, through
`isrRtxMemoryPoolAlloc`/`Free` (`Source/rtx_mempool.c` lines 684-732),
which check the object and then call `osRtxMemoryPoolAlloc` and
`osRtxMemoryPoolFree` (lines 113-185). Those two and
`osRtxMemoryPoolInit` (lines 77-108) hold the whole algorithm: a free list
with interrupts off where `EXCLUSIVE_ACCESS` is 0 (Armv6-M), and with
`atomic_link_get`/`atomic_link_put` (LDREX/STREX, `rtx_core_cm.h` lines
931-1001) where it is 1 (Armv7-M, Armv8-M; lines 47-57). The adapter
([`adapter_cmsis_rtx.c`](../pilot/pools-prechecks/adapter_cmsis_rtx.c))
calls the three directly.

**Cortex-M: built as it is** ([`cross.sh`](../pilot/pools-prechecks/cross.sh)).
`rtx_mempool.c` compiled unchanged for a Cortex-M4, a Cortex-M33 and a
Cortex-M0+, linked with `--gc-sections`:

```
cortex-m4 (ARMCM4): link ok
  undefined: none
  pool functions kept: osRtxMemoryPoolAlloc osRtxMemoryPoolFree osRtxMemoryPoolInit
  exclusive-access instructions:  1 clrex 1 dmb 4 ldrex 4 strex
cortex-m33 (ARMCM33): link ok
  undefined: none
  pool functions kept: osRtxMemoryPoolAlloc osRtxMemoryPoolFree osRtxMemoryPoolInit
  exclusive-access instructions:  1 clrex 1 dmb 4 ldrex 4 strex
cortex-m0plus (ARMCM0plus): link ok
  undefined: none
  pool functions kept: osRtxMemoryPoolAlloc osRtxMemoryPoolFree osRtxMemoryPoolInit
  exclusive-access instructions:  2 cpsid 2 cpsie
```

What it took, all of it:

- `OS_EVR_MEMORY=0`, the switch of `Config/RTX_Config.h` for the pool's
  Event Recorder calls ("RTOS Event Generation, Memory Management"). With
  it at 1 the three functions call `EvrRtxMemoryBlockInit`/`Alloc`/`Free`,
  which `Source/rtx_evr.c` defines as weak functions that are empty when
  the project has no Event Recorder (lines 302-309 for one of them); the
  link otherwise reports exactly those three symbols missing.
- `shims/RTE_Components.h`: the file a CMSIS pack project generates; here
  two defines that select RTX, nothing the pool reads.
- The device header (`CMSIS_device_header`) from Cortex_DFP, as a CMSIS
  project has it.

No kernel function is stubbed. The four LDREX/STREX pairs are the two link
operations and the increment and decrement of `used_blocks`.

**Host: the three functions, Armv6-M variant**
([`host.sh`](../pilot/pools-prechecks/host.sh)). `rtx_mempool.c` does not
compile for x86-64 as a whole: its public API calls the kernel through the
SVC macros of `rtx_core_cm.h`, which bind variables to the Arm registers
r0-r3 (gcc: "invalid register name for '__r0'"). So
[`extract.py`](../pilot/pools-prechecks/extract.py) copies the include line
and the three functions byte for byte (lines 77-108, 113-148, 154-185) and
checks that each copy occurs unchanged in the source. The host build is
the Armv6-M variant (`__ARM_ARCH_6M__`): the LDREX/STREX variant is Arm
inline assembly (check 2). The device header for the host
([`shims/host/ARMCM_host.h`](../pilot/pools-prechecks/shims/host/ARMCM_host.h))
gives `__get_PRIMASK`, `__disable_irq` and `__enable_irq` as a counted
flag, as the pilot's ThreadX host port does; everything else in it
(`__get_IPSR`, `SCB`, `__CLZ`, the exception numbers, ...) is used only by
inline functions the three do not call and is there so that the header
compiles. The pilot's host test
([`pilot/pools/test_pool.c`](../pilot/pools/test_pool.c), with
`POOL_TEST_CMSIS_RTX`; its own list unchanged otherwise, and its output
the same as on the pilot's day):

```
pool pilot test: 8 blocks of 32 bytes, 64 sequences of 20000 steps
reference free list (ours)         pass   (expected pass)  interrupt-off sections: 0
broken: block handed out twice     FAIL   (expected FAIL)  sequence 0, step 5: no block twice: a block handed out that the test holds
broken: block lost                 FAIL   (expected FAIL)  sequence 0, step 33: capacity: no block although fewer than POOL_BLOCKS are held
CMSIS-RTX osRtxMemoryPool (C)      pass   (expected pass)  interrupt-off sections: 1280867
exit 0: every verdict as expected
```

**What this does and does not say.** The pool runs without its kernel
with nothing faked on the path a pool block takes from an interrupt: the
object check and, after a free, `osRtxPostProcess` (which wakes a thread
waiting for a block) are the ISR call's additions that a test of the three
functions leaves out. A thread waiting for a block (`osMemoryPoolAlloc`
with a timeout) is the kernel's and is not tested this way. As for ThreadX
in the pilot, a reviewer may ask whether this is the pool users run; for
the interrupt path the code is the same.

## Check 2: LDREX/STREX on the host model

**The model** ([`verify/exclusive/excl_model.h`](../verify/exclusive/excl_model.h)).
The local exclusive monitor of one core: LDREX marks the address and sets
Exclusive Access; STREX stores and returns 0 only in Exclusive Access for
that address, else returns 1 without storing, and either way sets Open
Access; CLREX sets Open Access; exception entry and exception return set
Open Access. A plain store of the same core to the marked address is taken
not to clear the monitor (the choice that helps a program least; see
"Open" for the rule it rests on). A STREX to another address than the
marked one stops the check: a correct program does not do it, and the
model does not choose a behaviour for it. LDREX and STREX are each one
instruction on the core but several on the host; an interrupt point inside
one is held and taken right after it, as one held by PRIMASK is taken
after the unmask.

**The check** ([`verify/exclusive/excl_check.c`](../verify/exclusive/excl_check.c),
[`run.sh`](../verify/exclusive/run.sh)): the single-step method of the
contract check (`verify/contract`): main's call runs with the x86 trap
flag, and at host instruction k the signal handler makes the interrupt's
calls, for every k until main's call ends first. A made-up free list of
blocks (a stack, as RTX keeps its free blocks), its pop and push written
in C with the model, one statement per instruction of RTX's
`atomic_link_get`/`atomic_link_put`. Per trial a start stack of 0 to 3
blocks, main's pop or push, and the interrupt's pop, push, or pop, pop
and push of the first back (the A-B-A case). Verdict: every block exactly
once in the stack (a list that ends) or held by whoever popped it last.

```
LDREX/STREX in main and interrupt                    pass (expected pass)  1839 trials, 0 failed
broken: main pops with plain accesses                FAIL (expected FAIL)  1398 trials, 38 failed; first: stack of 1, main pop, interrupt pop, at instruction 12: pop returned node 1, held by 2
LDREX/STREX in main, plain in interrupt              pass (expected pass)  1839 trials, 0 failed
model control: the same, monitor kept at exception   FAIL (expected FAIL)  1839 trials, 151 failed; first: stack of 0, main push, interrupt push, at instruction 34: node 6 lost
LDREX/STREX everywhere, monitor kept at exception    pass (expected pass)  1839 trials, 0 failed
LDREX/STREX, a STREX failing without a cause         pass (expected pass)  8058 trials, 0 failed
broken: STREX's result ignored, STREX failing        FAIL (expected FAIL)  4674 trials, 1947 failed; first: stack of 0, main pop, interrupt push, at instruction 1, a STREX of main failing: node 6 in the stack and held by 1
exit 0: every verdict as expected
```

The last two lines are the mode for a STREX that fails without a cause
(below, "STREX failing without a cause"): at every interrupt point, each
of main's STREXes in turn fails although it would succeed (one per
trial), and in one trial the interrupt's first STREX that would succeed
fails. The correct list passes: a failed STREX is a retry. Its control, a
pop and a push that go on as if the STREX had stored, is caught.

The broken pop is caught. The model control shows that the rule "an
exception clears the monitor" carries the verdict where the interrupt
uses plain stores: without it, main's STREX succeeds on a stale value and a
block is lost. Where both sides use LDREX/STREX the interrupt's own STREX
clears the monitor, and the verdict does not depend on that rule.

**What the model can represent:** one core; the interrupt at every
instruction of main's call, one interrupt (with up to three calls) per
call; the monitor's states and the exception rule; an adversarial choice
where the implementation may choose (a plain store does not clear); and
safety under a STREX that fails without a cause, at the points tried
(each of main's STREXes in turn, and the interrupt's first).

**What it cannot represent:**

- More than one core or another bus master: no global monitor.
- The code the compiler makes for the target. The check runs a C
  transliteration of the assembly, one statement per instruction, compiled
  for the host. Whether a transliteration matches the library's assembly
  is a reading, not a check; for RTX the assembly is 20 lines
  (`atomic_link_get`, `atomic_link_put`). The hardware interrupt sweep
  (`firmware/nrf5340-rb-stress`) is what runs the real machine code.
- Progress: whether a loop of LDREX and STREX ends is not checked, only
  its safety; the mode above fails one STREX per trial, never every one.
- The reservation granule: the model marks one address exactly. On one
  core with the exception rule this matters only for a STREX to another
  address in the same granule, which the model stops on.
- Two interrupts in one call (nested or one after the other): not tried
  here; the contract check's two-interrupt mode would carry over.

## The model's rules in the Arm manuals

Checked against the ARMv7-M Architecture Reference Manual, ARM DDI 0403E.e
(ID021621), and the Armv8-M Architecture Reference Manual, DDI0553B.z
(ID06022026), both from developer.arm.com, read on 2026-11-24. Quoted
word for word.

**Exception entry and return clear the monitor.** The model: yes, both.

- DDI 0403E.e, A3.4.4 "Context switch support": "In Armv7-M, the local
  monitor is changed to Open Access automatically as part of an exception
  entry or exit sequence." The pseudocode agrees: `ExceptionTaken()`
  (B1.5.6 "Exception entry behavior") and `ExceptionReturn()` (B1.5.8
  "Exception return behavior") both call `ClearExclusiveLocal(ProcessorID());`.
- DDI0553B.z, B9.2 "The local monitors", rule RHRHC: "An exception return
  clears the local monitor." The pseudocode clears it on entry too:
  E2.1.122 `ExceptionTaken`, line 83, and E2.1.121 `ExceptionReturn`,
  line 73, both `ClearExclusiveLocal(ProcessorID());`.

**STREX's success and failure.** The model: in Exclusive Access for that
address it stores and returns 0, else it returns 1 without storing; either
way Open Access after.

- DDI 0403E.e, A3.4.1 "Exclusive access instructions and Non-shareable
  memory regions": "If the local monitor is in its Exclusive Access state
  • If the address of the Store-Exclusive is the same as the address that
  has been tagged in the monitor by an earlier Load-Exclusive, then the
  store takes place, otherwise it is IMPLEMENTATION DEFINED whether the
  store takes place. • A status value is returned to a register: — If the
  store took place the status value is 0. — Otherwise, the status value is
  1. • The local monitor of the executing processor transitions to its
  Open Access state. If the local monitor is in its Open Access state • No
  store takes place. • A status value of 1 is returned to a register.
  • The local monitor remains in its Open Access state."
- DDI0553B.z, B9.4 "Exclusive access instructions and the monitors", rule
  RDTRN: the same text for Armv8-M.

**STREX to another address than the marked one.** The model: stops the
check.

- DDI 0403E.e, A3.4.1: "If the local monitor is in its Exclusive Access
  state and a processor performs a Store-Exclusive to any address other
  than the last one from which it has performed a Load-Exclusive, it is
  IMPLEMENTATION DEFINED whether the store succeeds, but in all cases the
  local monitor is reset to its Open Access state. In Armv7-M, the store
  must be treated as a software programming error."

**A plain store to a marked address.** The model: does not clear the
monitor.

- DDI 0403E.e, A3.4.1: "If the write is to a physical address that is
  covered by its local monitor it is IMPLEMENTATION DEFINED whether the
  write affects the state of the local monitor." (Table A3-2 gives both
  outcomes for `Store(t)` as "IMPLEMENTATION DEFINED alternative
  actions".)
- DDI0553B.z, B9.2, rule RNJWC: "If the write is to a physical address
  that is marked as Exclusive Access by its local monitor, it is
  IMPLEMENTATION DEFINED whether the write affects the state of the local
  monitor." The same rule makes a write to an address that is not marked
  IMPLEMENTATION DEFINED too, while the monitor is in Exclusive Access
  (Armv7-M: "the write does not affect the state of the local monitor").
  The model's choice, no effect, is the one that lets a STREX succeed
  most often, so it is the one a wrong program is caught under.

**CLREX.** The model: Open Access.

- DDI 0403E.e, Table A3-2: in Exclusive Access, "CLREX — Clears tagged
  address. — Open Access."; the instruction's pseudocode (A7.7.23 "CLREX") is
  `ClearExclusiveLocal(ProcessorID());`.
- DDI0553B.z, C2.4.35 "CLREX": "Clear Exclusive clears the local record of
  the executing PE that an address has had a request for an exclusive
  access."

**The reservation granule.** The model: one address, exactly.

- DDI 0403E.e, A3.4.3 "Tagging and the size of the tagged memory block":
  "The Exclusives reservation granule is IMPLEMENTATION DEFINED between:
  • One word, in an implementation with a == 2. • 512 words, in an
  implementation with a == 11." and the note: "For the local monitor, one
  of the IMPLEMENTATION DEFINED options is for the monitor to treat any
  access as matching the address of the previous Load-Exclusive access."
- DDI0553B.z, B9.1, rule RJHMH: "... an IMPLEMENTATION DEFINED value that
  is of a power of 2 size, in the range 4 - 512 words."; B9.2, rule RWTHJ:
  "The local monitor does not hold any physical address, but instead
  treats any access as matching the address of the previous Load-Exclusive
  instruction."
- So on a real core a STREX to another address may succeed. The model
  stops on it instead; in Armv7-M it is "a software programming error"
  (above), and a correct program does not reach it.

**STREX failing without a cause.**

- DDI0553B.z, B9.2, rule RMRSD: "The architecture permits a local monitor
  to transition to the Open Access state as a result of speculation, or
  from some other cause." and, after the state diagram: "Any transition of
  the local monitor to the Open Access state that is not caused by the
  architectural execution of an operation shown here does not
  indefinitely delay forward progress of execution."
- DDI 0403E.e has no rule in these words; A3.4.4 says "A context switch
  might cause a subsequent Store-Exclusive to fail", and the
  IMPLEMENTATION DEFINED options above (a plain store clearing the
  monitor) are causes a program does not see.
- The model does this in a mode of its own (`vl_excl_fail_nth`,
  `vl_excl_fail_isr` in `excl_model.h`): a STREX that the rules above
  would let succeed fails instead, at the points the check chooses (the
  last two lines of the output above). Without that mode it never fails
  such a STREX.

**Usage restrictions** (DDI 0403E.e, A3.4.5): "code must avoid placing an
explicit store between an LDREX and an STREX in a single code sequence",
and "an LDREX/STREX pair can only be relied on to eventually succeed if
they are executed with the same address". RTX's `atomic_link_get` has a
load between the two, no store; `atomic_link_put` stores before its LDREX.

## Open

- Progress of an LDREX/STREX loop under repeated failures: not checked.
- RTX's own `atomic_link_get`/`atomic_link_put` transliterated and run
  through the model (with the pool's three functions), as the next step
  if A goes ahead.

## Files

[`pilot/pools-prechecks/`](../pilot/pools-prechecks/): `libs.lock`,
`fetch.sh`, `run.sh` (both parts of check 1 in the toolchain image
`verified-libs/toolchain:2026-11-13`), `cross.sh`, `host.sh`,
`extract.py`, `adapter_cmsis_rtx.c`, `cross_main.c`, `shims/`.
[`verify/exclusive/`](../verify/exclusive/): `excl_model.h`,
`excl_check.c`, `run.sh` (host gcc, as `verify/contract`).
