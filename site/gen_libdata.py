#!/usr/bin/env python3
"""Collect the numbers of the interactive comparison page into site/data/libs.json.

Usage (on the lab host, where the records are):
  python3 site/gen_libdata.py [--bench GLOB] [CAMPAIGN_DIR ...]

Sources:
- speed: the newest benchmark record per board matching GLOB (default
  ~/lab-runs/*-rb-bench-flash-*.json; code in flash, cache or flash
  accelerator on, the record's own compiler flags), mean cycles per call;
- ISR stress: the campaign directories given (default: the newest
  ~/lab-runs/overnight-<stamp>-<board> per board, together with the nights
  before it as long as the stress test is unchanged: same SAME_TEST_PATHS
  at the campaigns' commits, see same_test), valid
  runs only, by the rules of firmware/nrf5340-rb-stress/summarize.py; a run
  in which a library was starved in a direction (the record's "starved":
  the interrupt load left the other side too little time) or did not
  finish is not counted for that library unless it had errors, and is
  given as "not_counted" (method page: reported, never counted as a pass);
- placement range: site/data/placement.json (placement.py --json over the
  SHIFT=0..28 records of the same benchmark), the lowest and highest mean per
  number, only where its shift-0 record is the record shown; the same for the
  Rust set (placement-rust.json) and the multi-producer set (placement-mp.json);
- one-core contract check: site/data/contract.json (verify/contract/summary.py
  --json over the output of verify/contract/run.sh), per configuration and
  producer/consumer mode (CONTRACT_AS: where its name there differs);
- license, version, model check: site/data/libs-meta.json (by hand);
  repository and commit: firmware/nrf5340-rb-bench/libs.lock;
- labels (zero-copy API, documented for two cores, unsafe by its own
  documentation): firmware/nrf5340-rb-stress/decode.py.

The output is committed; site/build.py embeds it in compare.html and runs
its embargo check over it like over every page. The negative control, the
mutants and the benchmark baseline are left out.
"""
import argparse
import glob
import subprocess
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STRESS = os.path.join(ROOT, "firmware/nrf5340-rb-stress")
sys.path.insert(0, STRESS)
from decode import MULTICORE_DOCUMENTED, MUTANTS, UNSAFE_BY_OWN_DOCS, ZERO_COPY   # noqa: E402
from summarize import CONTROL, analyse                                            # noqa: E402
from summarize_all import BOARD_ORDER, board_of                      # noqa: E402

# lab board name -> firmware board (the prefix of the record file names)
FW = {"nrf5340dk": "nrf5340", "nucleo-g0b1re": "stm32g0b1", "nucleo-g474re": "stm32g474",
      "nucleo-h723zg": "stm32h723", "sam-d20-xpro": "samd20", "pico2": "rp2350"}


# verify/contract name -> (record name, modes) where it is not simply the record
# name without its language suffix, in mode SPSC
CONTRACT_AS = {
    "pxq SPSC": ("pxq RingBuffer_PackedState (C++)", ["SPSC"]),
    "pxq MPSC": ("pxq RingBuffer_PackedState (C++)", ["MPSC"]),
    "pxq SPMC": ("pxq RingBuffer_PackedState (C++)", ["SPMC"]),
    "pxq MPMC": ("pxq RingBuffer_PackedState (C++)", ["MPMC"]),
    "pxq MPSC reserve/commit": ("pxq RingBuffer_PackedState (C++)", ["MPSC reserve/commit"]),
    "heapless mpmc::Queue (Rust)": ("heapless spsc::Queue (Rust)", ["MPSC", "SPMC", "MPMC"]),   # the MPMC check covers two producers and two consumers
}


def contract_by_record(path, names):
    """{record name: {mode: {verdict, trials}}} and the run's facts, from contract.json."""
    if not os.path.exists(path):
        return {}, None
    c = json.load(open(path))
    by_rec = {}
    for cname, v in c["configs"].items():
        rec, modes = CONTRACT_AS.get(cname, (None, ["SPSC"]))
        if rec is None:
            rec = next((n for n in names if cname in (n, re.sub(r" \((C\+\+|C|Rust)\)$", "", n))), None)
        if rec is None:
            sys.exit(f"{path}: {cname!r} matches no configuration (add it to CONTRACT_AS)")
        for mode in modes:
            by_rec.setdefault(rec, {})[mode] = v
    return by_rec, {k: c[k] for k in ("commit", "date", "trials", "interrupts_per_call")}


def mean(res, scenario, side):
    v = (res.get(scenario + "/cache_on") or {}).get(side)
    return v["mean"] if v else None


# What makes two campaigns the same test: everything the ISR stress firmware
# is built and decoded from (its directory, the board layers, the benchmark
# directory with the adapters and the pinned libraries, the Rust adapters) and
# the rotation of flags (night-all.sh). Pages, reports, other tools and the
# other test firmwares may differ.
SAME_TEST_PATHS = ["firmware/nrf5340-rb-stress", "firmware/common", "firmware/nrf5340-rb-bench",
                   "firmware/rust-adapters", "lab/tools/night-all.sh"]


def campaign_commit(d):
    """The one source commit of a campaign's records, or None (none recorded,
    several, unknown or with uncommitted changes)."""
    cs = set()
    for f in glob.glob(os.path.join(d, "*-rb-stress-*.json")):
        cs.add(json.load(open(f)).get("source_commit"))
    if len(cs) != 1:
        return None
    c = cs.pop()
    return None if not c or c == "unknown" or c.endswith("+dirty") else c


def same_test(c1, c2):
    if c1 == c2:
        return True
    r = subprocess.run(["git", "-C", ROOT, "diff", "--quiet", c1, c2, "--", *SAME_TEST_PATHS])
    return r.returncode == 0


def campaign_dirs(given):
    """Board -> list of campaign directories, newest first. Given directories
    are used as they are; otherwise the newest per board and the nights before
    it, back to the first one whose stress test differs."""
    out = {}
    if given:
        for d in given:
            out.setdefault(board_of(d), []).append(d)
        return {b: sorted(v, reverse=True) for b, v in out.items()}
    allc = {}
    for d in sorted(glob.glob(os.path.expanduser("~/lab-runs/overnight-*Z-*"))):
        if os.path.exists(os.path.join(d, "runs.tsv")):
            allc.setdefault(board_of(d), []).append(d)
    for b, ds in allc.items():
        ds = ds[::-1]
        keep, c0 = [ds[0]], campaign_commit(ds[0])
        for d in ds[1:]:
            c = campaign_commit(d)
            if not c0 or not c or not same_test(c0, c):
                break
            keep.append(d)
        out[b] = keep
    return out


def placement_range(figs):
    """Lowest and highest mean over the placement shifts, per number the page shows."""
    out = {}
    for key in ("push", "pop", "dma_w", "dma_r"):
        if key in figs:
            out[key] = [figs[key]["min"], figs[key]["max"]]
    if "block" in figs and "block_pop" in figs:   # the page's block number: mean of write and read, per byte
        w, r = figs["block"]["by_shift"], figs["block_pop"]["by_shift"]
        v = [(w[s] + r[s]) / 2 for s in w]
        out["block"] = [round(min(v), 2), round(max(v), 2)]
    return out


def lock_entries():
    out = {}
    for line in open(os.path.join(ROOT, "firmware/nrf5340-rb-bench/libs.lock")):
        f = line.split()
        if len(f) >= 3 and not line.startswith("#"):
            out[f[0]] = (re.sub(r"\.git$", "", f[1]), f[2])
    return out


def nrf5_lock():
    """The nRF5 SDK (nrf5-sdk.lock): a zip pinned by SHA-256, not a git commit."""
    f = {}
    for line in open(os.path.join(ROOT, "firmware/nrf5340-rb-bench/nrf5-sdk.lock")):
        w = line.split()
        if len(w) == 2 and not line.startswith("#"):
            f[w[0]] = w[1]
    return "https://www.nordicsemi.com/Products/Development-software/nRF5-SDK", "sha256:" + f["sha256"]


def not_counted(records, valid):
    """{summarize.py's key: runs} of the valid runs in which the library was
    starved in a direction or did not finish, and had no errors."""
    out = {}
    for r in valid:
        rec = records[r["record"]]
        starved = {s.rsplit(" / ", 1)[0] for s in rec.get("starved", [])}
        for lib in rec["libs"]:
            n = lib["name"]
            if n == CONTROL or lib.get("n/a") or n in MUTANTS:
                continue
            if not (n in starved or lib.get("did_not_finish")):
                continue
            if any(lib[x]["errors"] for x in ("isr_to_main", "main_to_isr")):
                continue
            tags = []   # as summarize.py's analyse
            if rec.get("sweep") is not None:
                tags.append("sweep")
            if rec.get("smp", False):
                tags.append("SMP" if n in MULTICORE_DOCUMENTED else "SMP, single-core design")
            key = n + (f" [{', '.join(tags)}]" if tags else "")
            out[key] = out.get(key, 0) + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bench", default=os.path.expanduser("~/lab-runs/*-rb-bench-flash-*.json"))
    ap.add_argument("--mp-bench", default=os.path.expanduser("~/lab-runs/*-rb-bench-mp-flash-*.json"),
                    help="records of the SET=mp benchmark (modes for more than one producer or consumer)")
    ap.add_argument("--rust-bench", default=os.path.expanduser("~/lab-runs/*-rb-bench-rust-flash-*.json"),
                    help="records of the SET=rust benchmark (the Rust libraries, a firmware of their own)")
    ap.add_argument("--nordic-bench", default=os.path.expanduser("~/lab-runs/nrf5340-rb-bench-nordic-flash-*.json"),
                    help="records of the SET=nordic benchmark (Nordic's nrf_ringbuf, nRF5340 only, a firmware of its own)")
    ap.add_argument("--placement", default=os.path.join(HERE, "data/placement.json"),
                    help="the placement experiment (firmware/nrf5340-rb-bench/placement.py --json); used for a board "
                         "only if its shift-0 record is the benchmark record shown")
    ap.add_argument("--placement-rust", default=os.path.join(HERE, "data/placement-rust.json"),
                    help="the placement experiment of the SET=rust benchmark (same rule)")
    ap.add_argument("--placement-mp", default=os.path.join(HERE, "data/placement-mp.json"),
                    help="the placement experiment of the SET=mp benchmark (same rule)")
    ap.add_argument("--size", default=os.path.expanduser("~/lab-runs/*-rb-size-2*.json"),
                    help="records of firmware/nrf5340-rb-bench/size.sh (default flags): flash and RAM per configuration")
    ap.add_argument("--contract", default=os.path.join(HERE, "data/contract.json"),
                    help="the one-core contract check (verify/contract/summary.py --json)")
    ap.add_argument("--out", default=os.path.join(HERE, "data/libs.json"))
    ap.add_argument("campaigns", nargs="*")
    a = ap.parse_args()
    meta = json.load(open(os.path.join(HERE, "data/libs-meta.json")))
    lock = lock_entries()
    placement, pl_rust, pl_mp = (json.load(open(f)) if os.path.exists(f) else {}
                                 for f in (a.placement, a.placement_rust, a.placement_mp))
    dirs = campaign_dirs(a.campaigns)

    boards, libs, mpspeed, sizes = [], {}, {}, {}
    stress_pins = {}   # lock name -> commits the stress campaigns built (libs_pinned)
    for b in BOARD_ORDER:
        recs = sorted(f for f in glob.glob(a.bench) if os.path.basename(f).startswith(FW[b] + "-rb-bench-flash-2"))
        if not recs:
            print(f"note: no benchmark record for {b}", file=sys.stderr)
            continue
        r = json.load(open(recs[-1]))
        binfo = {"id": b, "name": r["board"], "core": r["core"], "clock_mhz": round(r["clock_hz"] / 1e6),
                 "bench": {"record": os.path.basename(recs[-1]), "time": r["time"], "commit": r.get("bench_commit"),
                           "opt": r["opt"], "compiler": r["compiler_libs"]}}
        for lib in r["libs"]:
            n, res = lib["name"], lib["results"]
            if n == "baseline":
                continue
            p64, q64 = mean(res, "block64", "push"), mean(res, "block64", "pop")
            libs.setdefault(n, {"speed": {}, "stress": {}, "smp": {}})["speed"][b] = {
                "push": mean(res, "single", "push"), "pop": mean(res, "single", "pop"),
                "block": round((p64 + q64) / 128, 2) if p64 and q64 else None,
                "dma_w": mean(res, "dma64", "push"), "dma_r": mean(res, "dma64", "pop")}
        pl = placement.get(r["board"])
        if pl and pl["records"].get("0") == os.path.basename(recs[-1]):
            binfo["bench"]["placement"] = {"shifts": pl["shifts"]}
            for n, figs in pl["libs"].items():
                if n in libs and b in libs[n]["speed"]:
                    libs[n]["speed"][b]["range"] = placement_range(figs)
        elif pl:
            print(f"note: {b}: the placement experiment is not from {os.path.basename(recs[-1])}, no ranges", file=sys.stderr)
        # SET=rust: the Rust libraries; baseline and pxq there are only the
        # reference against the SPSC set, whose numbers stay the ones shown
        rrecs = sorted(f for f in glob.glob(a.rust_bench) if os.path.basename(f).startswith(FW[b] + "-rb-bench-rust-flash-2"))
        if rrecs:
            rr = json.load(open(rrecs[-1]))
            binfo["rust_bench"] = {"record": os.path.basename(rrecs[-1]), "commit": rr.get("bench_commit"),
                                   "rustc": (rr.get("toolchain") or {}).get("rustc")}
            for lib in rr["libs"]:
                n, res = lib["name"], lib["results"]
                if not n.endswith("(Rust)"):
                    continue
                p64, q64 = mean(res, "block64", "push"), mean(res, "block64", "pop")
                libs.setdefault(n, {"speed": {}, "stress": {}, "smp": {}})["speed"][b] = {
                    "push": mean(res, "single", "push"), "pop": mean(res, "single", "pop"),
                    "block": round((p64 + q64) / 128, 2) if p64 and q64 else None,
                    "dma_w": mean(res, "dma64", "push"), "dma_r": mean(res, "dma64", "pop")}
            plr = pl_rust.get(rr["board"])
            if plr and plr["records"].get("0") == os.path.basename(rrecs[-1]):
                binfo["rust_bench"]["placement"] = {"shifts": plr["shifts"]}
                for n, figs in plr["libs"].items():
                    if n.endswith("(Rust)") and b in libs.get(n, {}).get("speed", {}):
                        libs[n]["speed"][b]["range"] = placement_range(figs)
            else:
                print(f"note: {b}: no placement experiment for {os.path.basename(rrecs[-1])}, no Rust ranges", file=sys.stderr)
        # SET=nordic (nRF5340 only, Nordic's licence): nrf_ringbuf; baseline
        # and pxq there are only the reference against the SPSC set
        nrecs = sorted(glob.glob(a.nordic_bench)) if b == "nrf5340dk" else []
        if nrecs:
            nr = json.load(open(nrecs[-1]))
            binfo["nordic_bench"] = {"record": os.path.basename(nrecs[-1]), "commit": nr.get("bench_commit")}
            for lib in nr["libs"]:
                n, res = lib["name"], lib["results"]
                if not n.startswith("Nordic "):
                    continue
                p64, q64 = mean(res, "block64", "push"), mean(res, "block64", "pop")
                libs.setdefault(n, {"speed": {}, "stress": {}, "smp": {}})["speed"][b] = {
                    "push": mean(res, "single", "push"), "pop": mean(res, "single", "pop"),
                    "block": round((p64 + q64) / 128, 2) if p64 and q64 else None,
                    "dma_w": mean(res, "dma64", "push"), "dma_r": mean(res, "dma64", "pop")}
        mrecs = sorted(f for f in glob.glob(a.mp_bench) if os.path.basename(f).startswith(FW[b] + "-rb-bench-mp-flash-2"))
        if mrecs:
            mr = json.load(open(mrecs[-1]))
            binfo["mp_bench"] = {"record": os.path.basename(mrecs[-1]), "commit": mr.get("bench_commit")}
            plm = pl_mp.get(mr["board"])
            if plm and plm["records"].get("0") == os.path.basename(mrecs[-1]):
                binfo["mp_bench"]["placement"] = {"shifts": plm["shifts"]}
            else:
                plm = None
                print(f"note: {b}: no placement experiment for {os.path.basename(mrecs[-1])}, no MP ranges", file=sys.stderr)
            for lib in mr["libs"]:
                res = lib["results"]
                p64, q64 = mean(res, "block64", "push"), mean(res, "block64", "pop")
                if mean(res, "single", "push") is None:   # not available on this core
                    continue
                mpspeed.setdefault(lib["name"], {})[b] = {
                    "push": mean(res, "single", "push"), "pop": mean(res, "single", "pop"),
                    "block": round((p64 + q64) / 128, 2) if p64 and q64 else None}
                if plm and lib["name"] in plm["libs"]:
                    mpspeed[lib["name"]][b]["range"] = placement_range(plm["libs"][lib["name"]])
        # size.sh: flash and RAM a configuration adds, where it exists on the core
        srecs = sorted(f for f in glob.glob(a.size) if os.path.basename(f).startswith(FW[b] + "-rb-size-2"))
        if srecs:
            sr = json.load(open(srecs[-1]))
            binfo["size"] = {"record": os.path.basename(srecs[-1]), "commit": sr.get("source_commit"),
                             "opt": sr["opt"], "compiler": sr["compiler_libs"]}
            sizes[b] = {e["name"]: {"flash": e["flash"], "ram": e["ram"], "heap": e["heap"]}
                        for e in sr["libs"] if e["available"]}
            for n, e in sizes[b].items():
                if n in libs and b in libs[n]["speed"]:
                    libs[n].setdefault("size", {})[b] = e
        if b in dirs:
            commits, nvalid, aggs = set(), 0, []
            for d in dirs[b]:
                _, records, valid, invalid, unfinished, agg = analyse(d)
                commits |= {rec.get("source_commit", "?") for rec in records.values()}
                for rec in records.values():
                    for pl in rec.get("libs_pinned", []):
                        f = pl.split()
                        if len(f) >= 2:
                            stress_pins.setdefault(f[0], set()).add(f[-1])
                nvalid += len(valid)
                for key, k in not_counted(records, valid).items():
                    agg[key]["not_counted"] = k
                aggs.append(agg)
            names = [os.path.basename(os.path.normpath(d)) for d in dirs[b]]
            binfo["stress"] = {"campaign": " + ".join(names), "campaigns": names, "valid_runs": nvalid,
                               "commit": ", ".join(sorted(commits))}
            for key, v in ((k, v) for agg in aggs for k, v in agg.items()):
                m = re.match(r"^(.*?)(?: \[(.*)\])?$", key)
                n, tags = m.group(1), (m.group(2) or "")
                if n not in libs:
                    continue
                kind = "smp" if "SMP" in tags else "stress"
                t = libs[n][kind].setdefault(b, {"runs": 0, "errors": 0, "runs_with_errors": 0})
                t["runs"] += v["runs"] - v.get("not_counted", 0)
                if v.get("not_counted"):
                    t["not_counted"] = t.get("not_counted", 0) + v["not_counted"]
                t["errors"] += v["errors"]
                t["runs_with_errors"] += len(v["runs_with_errors"])
        boards.append(binfo)

    hold_file = os.path.join(HERE, "data/hold.txt")   # configurations not shown for now (not in the public tree)
    hold = {l.strip() for l in open(hold_file) if l.strip() and not l.startswith("#")} if os.path.exists(hold_file) else set()
    contract, contract_run = contract_by_record(a.contract, list(libs))
    out = []
    for n, d in libs.items():
        if n in MUTANTS or n == CONTROL or n in hold:
            continue
        m = meta.get(n)
        if m is None:
            sys.exit(f"{n}: no entry in site/data/libs-meta.json")
        url, commit = lock[m["lock"]] if m["lock"] in lock else nrf5_lock()
        lang = re.search(r"\((C\+\+|C|Rust)\)$", n)
        mp = dict(m["mp"]) if m.get("mp") else None
        if mp:   # speed of each mode per board, all from the SET=mp records (one firmware per board);
            # a mode that is not available on a core has no numbers there
            src = mp.get("speed_from", {})
            mp["speed"] = {b["id"]: {mode: mpspeed.get(src.get(mode, n), {}).get(b["id"]) for mode in mp["modes"]}
                           for b in boards}
            mp["size"] = {b["id"]: {mode: sizes.get(b["id"], {}).get(src.get(mode, n)) if mp["speed"][b["id"]][mode] else None
                                    for mode in mp["modes"]} for b in boards}
            mp["other_code"] = bool(src)
            mp.pop("speed_from", None)
        # The stress campaign may have tested another commit of the library
        # than the one pinned now (a library update after the campaign):
        # named on the page, so the stress column is not read as this version's.
        tested = sorted(c for c in stress_pins.get(m["lock"], set()) if not commit.startswith(c))
        stress_other = [c[:8] for c in tested] if d["stress"] and tested else None
        out.append({"name": re.sub(r" \((C\+\+|C|Rust)\)$", "", n), "record_name": n, "lang": lang.group(1) if lang else "?",
                    "stress_tested_commits": stress_other,
                    "license": m["license"], "version": m.get("version"), "commit": commit[:15] if commit.startswith("sha256:") else commit[:8], "url": url,
                    "own": bool(m.get("own")), "genmc": m.get("genmc"), "mp": mp, "contract": contract.get(n),
                    "zero_copy": n in ZERO_COPY or any(v["dma_w"] for v in d["speed"].values()), "two_cores_documented": n in MULTICORE_DOCUMENTED,
                    "boards_only": m.get("boards_only"), "boards_only_why": m.get("boards_only_why"),
                    "unsafe_by_own_docs": n in UNSAFE_BY_OWN_DOCS, "single_context": "single-context" in n,
                    "size": {}, **d})
    out.sort(key=lambda x: x["name"].lower())
    json.dump({"boards": boards, "contract": contract_run, "libs": out}, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} configurations, {len(boards)} boards -> {a.out}")
    # A record whose commit is unknown or had uncommitted changes cannot be
    # rebuilt by lab/tools/verify-build.sh: say so (never publish such numbers).
    for bi in boards:
        for k in ("bench", "mp_bench", "rust_bench", "nordic_bench", "size"):
            if k not in bi:
                continue
            c = bi[k].get("commit") or "none"
            if c in ("none", "unknown") or c.endswith("+dirty"):
                print(f"WARNING: {bi['id']} {k} {bi[k]['record']}: commit {c}, cannot be rebuilt", file=sys.stderr)


if __name__ == "__main__":
    main()
