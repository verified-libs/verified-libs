# The exclusive-monitor model and its rules in the Arm manuals

[`excl_model.h`](excl_model.h) is a host model of a Cortex-M core's local
exclusive monitor (LDREX, STREX, CLREX). [`excl_check.c`](excl_check.c) runs
it in the one-core check with an interrupt at every instruction, as
[`../contract`](../contract) does; [`run.sh`](run.sh) builds and runs it with
the host's gcc, with no board and no toolchain image (exit 0 if every verdict
is as expected). The pools concurrency series' host check uses a copy widened
to 64-bit words ([`kinds/pools-isr/excl_host.h`](../../kinds/pools-isr/excl_host.h)).

The rules below were checked for the pools kind's prechecks on 2026-11-24.

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
  would let succeed fails instead, at the points the check chooses.
  Without that mode it never fails such a STREX.

**Usage restrictions** (DDI 0403E.e, A3.4.5): "code must avoid placing an
explicit store between an LDREX and an STREX in a single code sequence",
and "an LDREX/STREX pair can only be relied on to eventually succeed if
they are executed with the same address". RTX's `atomic_link_get` has a
load between the two, no store; `atomic_link_put` stores before its LDREX.
