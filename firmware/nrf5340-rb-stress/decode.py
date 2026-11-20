#!/usr/bin/env python3
"""Decode the nrf5340-rb-stress result block into a table and a JSON record.

Usage: decode.py WORDS_FILE META_JSON OUT_JSON [FW_LST FW_MAP]
FW_LST (objdump -d -C) and FW_MAP (linker map) are used in sweep mode
(result version + 0x200) to map the coverage bitmap to instructions.
Exit code 0 only if every real library (not counting configurations their own
documentation calls ISR-unsafe) has 0 errors AND the negative
control ("broken") is caught: in main -> ISR for single bytes, in both
directions for blocks.
"""
import json
import re
import sys

MAGIC = 0x564C5331
LIBS = ["pxq RingBuffer_PackedState (C++)", "lwrb (C)", "AndersKaloer Ring-Buffer (C)",
        "jnk0le Ringbuffer (C++)", "ETL queue_spsc_isr (C++)", "ETL queue_spsc_atomic (C++)",
        "QuantumLeaps LFRB (C)", "EmbeddedArtistry cbuf threadsafe (C)", "ece-mohammad RingBuffer (C)",
        "micoring SPSC mode (C)", "kostyk348 lf_spsc (C)", "diffstorm cb (C)", "RIOT tsrb (C)",
        "Contiki-NG ringbuf (C)", "rigtorp SPSCQueue (C++)", "wizard97 as shipped (C++)",
        "wizard97 + PRIMASK macros (C++)", "polycratia spscring (C++)", "rt-spsc (C++)",
        "TinyUSB tu_fifo (C)", "Zephyr ring_buf (C)", "Zephyr ring_buf, CONFIG_SMP (C)",
        "DNedic lockfree spsc::RingBuf (C++)", "ETL queue_spsc_locked (C++)", "FreeRTOS stream buffer (C)",
        "NuttX circbuf (C)", "Arduino RingBufferN as shipped (C++)", "Arduino SafeRingBufferN (C++)",
        "RT-Thread rt_ringbuffer, no lock (C)", "RT-Thread rt_ringbuffer + interrupt lock (C)", "Mbed CE CircularBuffer (C++)", "moodycamel ReaderWriterQueue (C++)",
        "heapless spsc::Queue (Rust)", "bbqueue (Rust)", "embassy-sync Pipe (Rust)",
        "broken (negative control)",
        "mutant: shared count, no lock", "mutant: shared count, pop without lock",
        "mutant: full test misses the wrap", "mutant: drain re-reads head",
        # 40: only in the NORDIC=1 firmware (nRF5340 only, Nordic's licence)
        "Nordic nrf_ringbuf (C)"]
# Mutants (mutants.c): other bug classes, reported per direction as caught or
# not; they do not decide whether a run counts (the control does).
MUTANTS = {n for n in LIBS if n.startswith("mutant: ")}
# Configurations their own documentation calls unsafe for ISR use; reported,
# but not counted as "real libraries" in the pass/fail verdict.
UNSAFE_BY_OWN_DOCS = {"wizard97 as shipped (C++)",
                      # its maintainers: not meant to be thread-safe (ArduinoCore-API #195)
                      "Arduino RingBufferN as shipped (C++)",
                      # no concurrency claim; RT-Thread's own serial driver locks around it
                      "RT-Thread rt_ringbuffer, no lock (C)"}
# Libraries with a zero-copy API (DMA mode, result version 3); the others are
# skipped by the firmware and reported as n/a.
ZERO_COPY = {"pxq RingBuffer_PackedState (C++)", "lwrb (C)", "ece-mohammad RingBuffer (C)",
             "TinyUSB tu_fifo (C)", "Zephyr ring_buf (C)", "Zephyr ring_buf, CONFIG_SMP (C)",
             "NuttX circbuf (C)", "bbqueue (Rust)", "broken (negative control)"}
BOARDS = {1: "nRF5340 DK, application core (Cortex-M33)",
          2: "NUCLEO-G0B1RE (STM32G0B1RET6, Cortex-M0+)",
          3: "NUCLEO-G474RE (STM32G474RET6, Cortex-M4F)",
          4: "NUCLEO-H723ZG (STM32H723ZGT6, Cortex-M7)",
          5: "SAM D20 Xplained Pro (ATSAMD20J18A, Cortex-M0+)",
          6: "Raspberry Pi Pico 2 H (RP2350A, Cortex-M33)"}
# SMP mode (result version + 0x100, RP2350: the other side runs on core 1):
# only libraries that are built for concurrent threads/cores (C11 or C++
# atomics; the ones GenMC checks) are in their documented mode there. The
# others are single-core (interrupt) designs; their results are reported
# but not counted.
MULTICORE_DOCUMENTED = {"lwrb (C)", "jnk0le Ringbuffer (C++)", "ETL queue_spsc_atomic (C++)",
                        "QuantumLeaps LFRB (C)", "micoring SPSC mode (C)", "kostyk348 lf_spsc (C)",
                        "diffstorm cb (C)", "rigtorp SPSCQueue (C++)", "polycratia spscring (C++)",
                        "rt-spsc (C++)", "Zephyr ring_buf, CONFIG_SMP (C)",
                        "DNedic lockfree spsc::RingBuf (C++)", "moodycamel ReaderWriterQueue (C++)",
                        # Rust: Send/Sync types on atomics (bbqueue: its atomic flavour,
                        # chosen where the core has compare-and-swap, as on the RP2350)
                        "heapless spsc::Queue (Rust)", "bbqueue (Rust)"}
DIRS = ["isr_to_main", "main_to_isr"]
FIELDS = ["transferred", "errors", "first_error_at", "first_error_got", "first_error_want",
          "full_events", "empty_events", "irqs"]


def masked_pcs(ins, effect):
    """PCs that cannot be the interrupted PC because interrupts are masked
    when the instruction there is reached. Flow-sensitive over the function:
    cpsid masks; cpsie unmasks; mrs rN, PRIMASK saves the state in rN and
    msr PRIMASK, rN restores it (nested critical sections); bl to a lock or
    unlock helper masks or unmasks. Where two paths meet with different
    states the instruction counts as masked."""
    pos = {a: i for i, (a, _, _) in enumerate(ins)}
    state = {}                      # index -> (inside, saved regs)
    work = [(0, (False, ()))]
    while work:
        i, st = work.pop()
        if i >= len(ins):
            continue
        old = state.get(i)
        if old is not None:
            merged = (old[0] or st[0], old[1] if old[1] == st[1] else ())
            if merged == old:
                continue
            st = merged
        state[i] = st
        a, op, args = ins[i]
        inside, saved = st
        saved = dict(saved)
        toks = args.replace(",", " ").split()
        # Branch target: the first bare hex token ("cbz r2, 8002f7e <f+0x1e>",
        # "b.n 8002f78 <f+0x18>", "bl 8003000 <lock>"); the register of a
        # cbz/cbnz comes first and the <symbol+off> label last.
        tgt = None
        for t in (toks[1:] if op.startswith("cb") else toks[:1]):
            if re.fullmatch(r"[0-9a-f]+", t):
                tgt = int(t, 16)
                break
        if op == "cpsid":
            inside = True
        elif op == "cpsie":
            inside = False
        elif op == "mrs" and "primask" in args.lower():
            saved[toks[0]] = inside
        elif op == "msr" and "primask" in args.lower():
            inside = saved.get(toks[-1], False)
        elif op == "bl" and effect.get(tgt) == "lock":
            inside = True
        elif op == "bl" and effect.get(tgt) == "unlock":
            inside = False
        nst = (inside, tuple(sorted(saved.items())))
        ret = (op == "bx" or (op.startswith("pop") and "pc" in args) or (op.startswith("ldm") and "pc" in args))
        uncond = op in ("b", "b.n", "b.w")
        cond = (op.startswith("b") and op not in ("bl", "blx", "bx", "bic", "bics", "bfi", "bfc", "bkpt")
                and not uncond) or op.startswith("cb")
        if (uncond or cond) and tgt in pos:
            work.append((pos[tgt], nst))
        if not ret and not uncond:
            work.append((i + 1, nst))
    return {ins[i][0] for i, st in state.items() if st[0]}


def sweep_coverage(cov_bits, cov_base, lst_file, map_file):
    """Per function: instructions (start addresses from the listing), how many
    were the interrupted PC at least once, and how many lie where interrupts
    are masked (masked_pcs: reached with PRIMASK set; the interrupt is taken
    before the instruction at the PC, so those PCs cannot occur). Object
    file per function from the map."""
    objs = []   # (start, end, object)
    with open(map_file) as fh:
        lines = fh.read().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^ \.text\S*\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+\.o)", ln)
        if not m and re.match(r"^ \.text\S*\s*$", ln) and i + 1 < len(lines):
            m = re.match(r"^\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(\S+\.o)", lines[i + 1])
        if m:
            a, n = int(m.group(1), 16), int(m.group(2), 16)
            if n:
                objs.append((a, a + n, m.group(3).split("/")[-1].split("(")[0]))
    def obj_of(addr):
        for a, e, o in objs:
            if a <= addr < e:
                return o
        return "?"
    funcs = []
    cur = None
    with open(lst_file) as fh:
        lst_lines = fh.read().splitlines()
    for ln in lst_lines:
        m = re.match(r"^([0-9a-f]{8}) <(.+)>:$", ln)
        if m:
            cur = {"name": m.group(2), "addr": int(m.group(1), 16), "insns": []}
            funcs.append(cur)
            continue
        # no leading blank when the address has 8 digits (RP2350: 0x10000000)
        m = re.match(r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s?){1,2}\s+(\S+)(.*)$", ln)
        if cur is not None and m:
            cur["insns"].append((int(m.group(1), 16), m.group(2), m.group(3).strip()))
    def hit(addr):
        off = (addr - cov_base) >> 1
        return 0 <= off < len(cov_bits) * 32 and (cov_bits[off >> 5] >> (off & 31)) & 1
    def is_unmask(op, args):
        return op == "cpsie" or (op == "msr" and "primask" in args.lower())
    # Functions that leave interrupts masked (a cpsid with no unmask after it)
    # or unmasked (an unmask with no cpsid after it): lock / unlock helpers.
    effect = {}
    for f in funcs:
        last = None
        for a, op, args in f["insns"]:
            if op == "cpsid":
                last = "lock"
            elif is_unmask(op, args):
                last = "unlock"
        if last:
            effect[f["addr"]] = last
    out = []
    for f in funcs:
        ins = [x for x in f["insns"] if not x[1].startswith(".")]
        if not ins:
            continue
        covered = [a for a, _, _ in ins if hit(a)]
        if not covered:
            continue
        # Masked: the instructions after a cpsid (or a bl to a lock helper) up
        # to and including the unmask (or the bl to an unlock helper); the
        # interrupt is taken before the instruction at the PC, so these PCs
        # cannot occur. Indirect calls (blx rN) cannot be resolved here: a run
        # of instructions that were never interrupted, from just after one
        # indirect call up to and including the next, is reported as
        # "probably masked" (a lock and an unlock called through pointers, as
        # in ETL's queue_spsc_locked). Padding: nops after the last return.
        masked = masked_pcs(ins, effect)
        probably = set()
        def ends_flow(op, args):
            return (op in ("b", "b.n", "b.w", "bx") or (op.startswith("pop") and "pc" in args)
                    or (op.startswith("ldm") and "pc" in args))
        k = 0
        while k < len(ins):
            if hit(ins[k][0]) or ins[k][0] in masked:
                k += 1
                continue
            j = k
            while j + 1 < len(ins) and not hit(ins[j + 1][0]) and ins[j + 1][1] != "blx":
                j += 1
            if j + 1 < len(ins) and ins[j + 1][1] == "blx" and not hit(ins[j + 1][0]):
                j += 1
            prev = ins[k - 1] if k else None
            if (ins[j][1] == "blx" and prev is not None
                    and (prev[1] == "blx" or ends_flow(prev[1], prev[2]))):
                probably.update(a for a, _, _ in ins[k:j + 1])
            k = j + 1
        padding = set()
        for a, op, args in reversed(ins):
            if op in ("nop", "nop.n", "nop.w"):
                padding.add(a)
            else:
                break
        excluded = masked | probably | padding
        uncovered = [a for a, _, _ in ins if not hit(a) and a not in excluded]
        out.append({"function": f["name"], "object": obj_of(f["addr"]), "addr": f"{f['addr']:#010x}",
                    "instructions": len(ins) - len(padding), "interrupted": len(covered),
                    "masked": len(masked - padding), "probably_masked": len(probably - masked - padding),
                    "not_interrupted": [f"{a:#x}" for a in uncovered]})
    return out


def main():
    words_file, meta_file, out_file = sys.argv[1:4]
    images = None
    if sys.argv[4:5] == ["--images"]:
        # one image per library (run.sh, ../common/bundle.py): a JSON object
        # {index: {"words": block, "lst": listing, "map": map}}; each
        # library's coverage comes from its own block and its own image
        images = {int(k): v for k, v in json.load(open(sys.argv[5])).items()}
        lst_file = map_file = None
    else:
        lst_file, map_file = (sys.argv[4:6] + [None, None])[:2]
    w = [int(x, 16) for x in open(words_file).read().split()]
    magic, version, done, transfers, nlibs, ndirs = w[:6]
    smp = bool(version & 0x100)
    sweep = bool(version & 0x200)
    double = bool(version & 0x400)   # sweep=2: two interrupts per call
    version &= 0xFF
    if magic != MAGIC:
        sys.exit(f"bad magic {magic:#010x}")
    if done != 1:
        sys.exit("stress test not finished")
    pos = 6
    libs = []
    for name in LIBS[:nlibs]:
        lib = {"name": name}
        for d in DIRS[:ndirs]:
            lib[d] = dict(zip(FIELDS, w[pos:pos + len(FIELDS)]))
            pos += len(FIELDS)
        libs.append(lib)

    main_seed, isr_seed, prescaler, cache_on, code_in_sram = w[pos:pos + 5]
    # appended in layout 2026-11-07: board id and clock; older records: nRF5340
    board_id, clock_hz = (w[pos + 5:pos + 7] if len(w) >= pos + 7 else (1, 64_000_000))
    if board_id not in BOARDS:
        sys.exit(f"unknown board id {board_id}")
    sw = None
    if sweep:
        q = pos + 7
        reps, cov_base, cov_words, cov_outside = w[q:q + 4]; q += 4
        cap = w[q:q + nlibs]; q += nlibs
        arr = []
        for _ in range(8):
            arr.append([w[q + 2 * i:q + 2 * i + 2] for i in range(nlibs)]); q += 2 * nlibs
        overlapped, sweeps, dsum, count_mm, count_lost, count_extra, cm_want, cm_got = arr
        cov_bits = w[q:q + cov_words]
        for i, lib in enumerate(libs):
            lib["capacity_bytes"] = cap[i]
            for k, d in enumerate(DIRS[:ndirs]):
                lib[d]["trials"] = lib[d]["irqs"]
                lib[d]["interrupted_during_call"] = overlapped[i][k]
                lib[d]["sweeps"] = sweeps[i][k]
                lib[d]["mean_last_delay_cycles"] = round(dsum[i][k] / sweeps[i][k], 1) if sweeps[i][k] else None
                lib[d]["count_mismatches"] = count_mm[i][k]   # drains with the wrong byte count
                lib[d]["count_bytes_lost"] = count_lost[i][k]     # summed over those drains
                lib[d]["count_bytes_extra"] = count_extra[i][k]
                if count_mm[i][k]:
                    lib[d]["count_first_mismatch"] = {"expected": cm_want[i][k], "drained": cm_got[i][k]}
                lib[d]["errors"] += count_mm[i][k]            # errors = byte errors + count mismatches
        sw = {"start_positions": reps, "fill_states": ["empty", "1 byte", "half", "full - 1", "full"],
              "coverage_base": f"{cov_base:#010x}", "pcs_outside_bitmap": cov_outside,
              "pcs_interrupted": sum(bin(x).count("1") for x in cov_bits),
              # raw bitmap (bit n = PC coverage_base + 2n was interrupted), so
              # the coverage can be recomputed from a rebuild of the same commit
              "bitmap_hex": "".join(f"{x:08x}" for x in cov_bits)}
        if smp:   # core 1 makes the other call: no interrupted PC, no coverage
            sw["coverage"] = "n/a: SMP sweep (the other side runs on core 1)"
            sw.pop("bitmap_hex", None)
            if images:
                sw["coverage_base"] = None   # one per image
        elif images:
            # Per library, from its own block and image: the merged block's
            # bitmap would mix images at different addresses.
            for k in ("coverage_base", "pcs_outside_bitmap", "pcs_interrupted", "bitmap_hex"):
                sw.pop(k)
            sw["per_library"], sw["functions"] = [], []
            q0 = pos + 7
            for l in sorted(images):
                bw = [int(x, 16) for x in open(images[l]["words"]).read().split()]
                base, cw, outside = bw[q0 + 1], bw[q0 + 2], bw[q0 + 3]
                c0 = q0 + 4 + nlibs + 8 * nlibs * ndirs
                bits = bw[c0:c0 + cw]
                sw["per_library"].append({"library": LIBS[l], "coverage_base": f"{base:#010x}",
                                          "pcs_outside_bitmap": outside,
                                          "pcs_interrupted": sum(bin(x).count("1") for x in bits),
                                          "bitmap_hex": "".join(f"{x:08x}" for x in bits)})
                for f in sweep_coverage(bits, base, images[l]["lst"], images[l]["map"]):
                    sw["functions"].append({"library": LIBS[l], **f})
        elif lst_file and map_file:
            sw["functions"] = sweep_coverage(cov_bits, cov_base, lst_file, map_file)
    for lib in libs:
        lib["n/a"] = version == 3 and lib["name"] not in ZERO_COPY
    # PER_LIB=1 (run.sh): one library per reset; the ones that did not finish
    # in their time limit (hung, crashed or too slow) are named in the meta data
    meta = json.load(open(meta_file))
    unfinished = set((meta.get("per_lib") or {}).get("unfinished", []))
    # run.sh LIBS: libraries not run at all; never counted as passed, and the
    # record is marked partial (campaigns and the site never use LIBS)
    not_run = set((meta.get("per_lib") or {}).get("not_run", []))
    for i, lib in enumerate(libs):
        if i in unfinished:
            lib["did_not_finish"] = True
        if i in not_run:
            lib["not_run"] = True
    params = {"main_seed": f"{main_seed:#010x}", "isr_seed": f"{isr_seed:#010x}",
              "timer_prescaler": prescaler, "isr_period_cycles": [4 * 40 << prescaler, 4 * 167 << prescaler],
              "cache_on": bool(cache_on), "code_in_sram": bool(code_in_sram),
              "board_id": board_id, "board_decoded": BOARDS[board_id], "clock_hz": clock_hz}
    record = {"schema": "nrf5340-rb-stress/0.2", "transfers": transfers, "params": params, "libs": libs,
              **meta}
    if sweep:
        record["sweep"] = sw
        params.pop("isr_period_cycles", None)
        params.pop("timer_prescaler", None)
        params.pop("isr_seed", None)
    json.dump(record, open(out_file, "w"), indent=2)

    mode = {1: "single bytes (push/pop)", 2: "blocks (push_n/pop_n; 1-16 bytes per call in main, 1-4 in the ISR)",
            3: "zero-copy (acquire/commit, acquire/release; 1-16 bytes per transfer in main, 1-4 in the ISR)"
            }.get(version, f"version {version}")
    if smp:
        mode += "; SMP: the other side runs on core 1 (no interrupt; 'irqs' = core-1 loop turns)"
    if sweep:
        mode += (("; SMP sweep: core 1 makes one call per trial, 0, 1, 2 ... delay steps (about one cycle each) after the start, "
                  if smp else
                  "; two-interrupt sweep: a first SysTick interrupt at every delay 1, 2, 3 ... cycles into the call and, "
                  "while it lands inside the call, a second one at every delay 1, 2, 3 ... cycles after the first "
                  "handler ('interrupted_during_call' = both inside), " if double else
                  "; interrupt sweep: one SysTick interrupt per call at every delay 1, 2, 3 ... cycles, ")
                 + f"5 fill states x {sw['start_positions']} start positions ('irqs' = trials)")
    record["mode"] = mode
    record["smp"] = smp
    if sweep:
        record["sweep"]["interrupts_per_call"] = 2 if double else 1
    json.dump(record, open(out_file, "w"), indent=2)
    print(f"{BOARDS[board_id]}, {clock_hz // 1_000_000} MHz")
    if sweep:
        print(f"{mode}; cache {'on' if cache_on else 'off'}, code in {'SRAM' if code_in_sram else 'flash'}")
    else:
        print(f"{transfers} bytes per library and direction, {mode}; seeds {params['main_seed']}/{params['isr_seed']}, "
              f"ISR every {params['isr_period_cycles'][0]}-{params['isr_period_cycles'][1]} cycles, "
              f"cache {'on' if cache_on else 'off'}, code in {'SRAM' if code_in_sram else 'flash'}")
    print(f"{'library':34} {'direction':12} {'bytes':>8} {'errors':>7} {'full':>8} {'empty':>9} {'irqs':>8}  first error")
    for lib in libs:
        if lib.get("not_run"):
            continue
        if lib["n/a"]:
            print(f"{lib['name']:34} n/a (no zero-copy API)")
            continue
        if lib.get("did_not_finish"):
            print(f"{lib['name']:34} DID NOT FINISH in its time limit (hung, crashed or too slow); counts so far:")
        for d in DIRS[:ndirs]:
            r = lib[d]
            cm = r.get("count_mismatches", 0)
            fe = (f"at byte {r['first_error_at']}: got {r['first_error_got']} want {r['first_error_want']}"
                  if r["errors"] > cm else "-")
            if cm:
                fm = r["count_first_mismatch"]
                fe += (f"; {cm} drains with the wrong byte count: {r['count_bytes_lost']} bytes lost, "
                       f"{r['count_bytes_extra']} too many (first: {fm['drained']} drained, {fm['expected']} expected)")
            extra = (f"  during call {r['interrupted_during_call']}, last delay ~{r['mean_last_delay_cycles']}"
                     if sweep else "")
            print(f"{lib['name']:34} {d:12} {r['transferred']:8} {r['errors']:7} {r['full_events']:8} "
                  f"{r['empty_events']:9} {r['irqs']:8}  {fe}{extra}")

    starved = [(lib["name"], d) for lib in libs if not lib["n/a"] and not lib.get("did_not_finish") and not lib.get("not_run")
               for d in DIRS[:ndirs] if lib[d]["transferred"] < transfers]
    for name, d in starved:
        print(f"note: {name} {d}: starved (the other side left the main loop too little time), not counted")
    record["starved"] = [f"{n} / {d}" for n, d in starved]
    if sweep and sw.get("functions") is not None:
        fs = sw["functions"]
        tot = sum(f["instructions"] - f["masked"] - f["probably_masked"] for f in fs)
        got = sum(f["interrupted"] for f in fs)
        full = sum(1 for f in fs if not f["not_interrupted"])
        print(f"coverage: {len(fs)} functions interrupted at least once; {got} of {tot} instructions outside "
              f"masked sections were the interrupted PC; {full} functions completely (instructions on paths "
              f"a sweep never executes count as not interrupted); "
              f"{sw.get('pcs_outside_bitmap', sum(e['pcs_outside_bitmap'] for e in sw.get('per_library', [])))} "
              f"PCs outside the bitmap{' (one image per library: functions per image)' if 'per_library' in sw else ''}")
        for f in sorted(fs, key=lambda f: -len(f["not_interrupted"]))[:12]:
            if f["not_interrupted"]:
                fn = (f"[{f['library'][:18]}] " if "library" in f else "") + f["function"]
                print(f"  {fn[:60]:60} {f['object']:24} {f['interrupted']:4}/{f['instructions'] - f['masked'] - f['probably_masked']:<4}"
                      f" not: {' '.join(f['not_interrupted'][:6])}{' ...' if len(f['not_interrupted']) > 6 else ''}")
    json.dump(record, open(out_file, "w"), indent=2)
    def counted(name):
        if "broken" in name or name in UNSAFE_BY_OWN_DOCS or name in MUTANTS:
            return False
        return name in MULTICORE_DOCUMENTED if smp else True
    real_ok = all(lib[d]["errors"] == 0 for lib in libs if counted(lib["name"]) for d in DIRS)
    hung = [lib["name"] for lib in libs if lib.get("did_not_finish") and counted(lib["name"])]
    for n in hung:
        print(f"note: {n} did not finish in its time limit: not error-free")
    real_ok = real_ok and not hung
    record["did_not_finish"] = [lib["name"] for lib in libs if lib.get("did_not_finish")]
    record["not_run"] = [lib["name"] for lib in libs if lib.get("not_run")]
    record["partial"] = bool(record["not_run"])
    if record["partial"]:
        print(f"note: partial run (LIBS): {len(libs) - len(record['not_run'])} of {len(libs)} libraries run; "
              "the others are not run, not passed")
    if smp:
        for lib in libs:
            if ("broken" not in lib["name"] and lib["name"] not in MULTICORE_DOCUMENTED
                    and lib["name"] not in MUTANTS):
                errs = sum(lib[d]["errors"] for d in DIRS)
                print(f"note: {lib['name']}: {errs} errors; single-core design, not in its documented mode here")
    for lib in libs:
        if lib["name"] in UNSAFE_BY_OWN_DOCS:
            errs = sum(lib[d]["errors"] for d in DIRS)
            print(f"note: {lib['name']}: {errs} errors; its documentation and maintainers do not claim it is ISR-safe in this configuration")
    caught = {}
    for lib in libs:
        if lib["name"] in MUTANTS and not lib["n/a"] and not lib.get("not_run"):
            caught[lib["name"]] = {d: lib[d]["errors"] > 0 for d in DIRS[:ndirs]}
    record["mutants_caught"] = caught
    if caught:
        print("mutants caught (isr_to_main / main_to_isr): " + "; ".join(
            f"{n[8:]}: {'yes' if c['isr_to_main'] else 'no'} / {'yes' if c['main_to_isr'] else 'no'}"
            for n, c in caught.items()))
    json.dump(record, open(out_file, "w"), indent=2)
    # Single bytes: the control's real bug is in push, so it must show when
    # main (the preemptible side) is the producer; its single-slot pop "bug"
    # is benign by design. Blocks: both of its bugs are real, so it must fail
    # in both directions. Zero-copy: its write area ignores the free space,
    # which overwrites unread data whenever the buffer is nearly full; the
    # main loop as producer outruns the ISR, so it must show in main -> ISR.
    must_fail = DIRS if version == 2 else ["main_to_isr"]
    control_caught = all(lib[d]["errors"] > 0 for lib in libs if "broken" in lib["name"] for d in must_fail)
    if smp:   # both sides run freely: the bug must show in at least one direction
        control_caught = any(lib[d]["errors"] > 0 for lib in libs if "broken" in lib["name"] for d in DIRS)
    print(f"\nreal libraries error-free: {real_ok}; negative control caught: {control_caught}")
    sys.exit(0 if real_ok and control_caught else 1)


if __name__ == "__main__":
    main()
