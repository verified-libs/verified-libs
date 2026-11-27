#!/usr/bin/env python3
"""Write site/data/crc.json, the data of the CRC kind for the comparison page
and the MCP server, from the records under records/crc, so that it cannot
drift from them: site/build.py refuses to build if the file is not what this
program writes.

Usage: python3 -I site/crc_data.py [--write | --check]
  (no argument: print the file; --write: write it; --check: exit 1 if it is
  not up to date)

Where each field comes from is in ABOUT below, which the file carries as
its "about". The second pass and the minimum, maximum and first call of each
scenario are in the records only.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import crc_tables   # noqa: E402
import series_info   # noqa: E402

OUT = os.path.join(ROOT, "site/data/crc.json")
LENS = (1, 4, 16, 64, 256, 1024)
LANG = {"c": "C", "cpp": "C++", "rust": "Rust"}
# The board ids of the ring buffers' data and the repeat scripts (kinds/crc/repeat.sh), by records directory.
SITE_ID = {"nrf5340": "nrf5340dk", "rp2350": "pico2", "stm32g474": "nucleo-g474re", "stm32h723": "nucleo-h723zg",
           "stm32g0b1": "nucleo-g0b1re", "samd20": "sam-d20-xpro"}   # configs.txt's language column, as the ring buffers' data names it
ABOUT = {
    "boards": "per board directory of records/crc (records_dir): id (the board's id in libs.json and in "
              "kinds/crc/repeat.sh), the record's board, board_decoded, core and clock_hz; method_version (3 for "
              "the records of crc-bench/2, with the board's option registers; 2 for crc-bench/1), archived (the "
              "series of records/archived.json that held this board's records before method version 3, where the "
              "present records replaced them; with its public commit), method_text (the sentence the pages put "
              "under the board's numbers; site/series_info.py); "
              "note_cache_off: the sentence the results page puts above the board's cache-off tables "
              "(site/crc_tables.py, before_off: by the board and the clock its records ran at), or null; "
              "note_hw_unit: the sentence about the board's CRC unit that the pages show where its row is shown "
              "(site/crc_tables.py, hw_unit_note: by the board and the clock), or null",
    "crcs": "the CRCs in the order of kinds/crc/configs.txt",
    "configurations": "per adapter, in the order of kinds/crc/configs.txt with the board's CRC units last: its language "
                      "(column 2: C, C++ or Rust) and library (column 3), "
                      "the name the record carries, its CRC, and class and table place (steps 2 and 11 of kinds/crc/README.md, "
                      "as site/crc_tables.py reads it); role: 'library', or 'hardware' for the board's CRC unit, driven by "
                      "our code and not a library (its library is null and its note says so, in its name cell every time); "
                      "a hardware row is a row of the same table, after the libraries of its CRC, and with weights it is "
                      "scored like any row (decided 2026-11-26, DECISIONS.md 2026-11-25); a filter on the kind of row "
                      "leaves it out. table 'RAM (copied at start by the image)': a library's table moved from flash to RAM "
                      "by our build (step 11), told apart from libraries that build their table in RAM themselves",
    "rows": "per board and configuration: flash_bytes (the table in flash plus the code at -O2 for the board's core) "
            "and ram_bytes (steps 4 and 11 of kinds/crc/README.md, as site/crc_tables.py; a table copied to RAM counts in "
            "both), the record's path, cycles and per_byte; hardware rows only on the boards that have the unit",
    "baseline": "per board and CRC: the reference of that CRC, timed in the same images (the records' baseline), "
                "cycles and per_byte over all images of the board's configurations of that CRC",
    "cycles": "cycles[cache][offset][length]: [min, max] over the eight placements, first pass, of the mean of the "
              "scenario's 256 calls (the first call included), in cycles; cache on/off, offset 0 (an 8-byte boundary) "
              "or 1, length 1 to 1024 bytes (the record's results, len<N>/offset<K>/cache_<off|on>)",
    "per_byte": "per_byte[cache][offset]: [min, max] over the eight placements, first pass, of (mean at 1024 bytes - "
                "mean at 256 bytes) / 768",
    "ranges": "a difference between two rows is a difference only where their ranges do not overlap "
              "(DECISIONS 2026-11-25); the rows are in the order of kinds/crc/configs.txt, not ranked",
    "not_here": "the second pass and the minimum, maximum and first call of each scenario: in the records",
}


def ranges(per_place):
    """placement -> results (one image's first run) -> the numbers as [min, max] over the placements"""
    def rng(vals):
        vals = [v for v in vals if v is not None]
        return [round(min(vals), 4), round(max(vals), 4)] if vals else None
    cyc, pb = {}, {}
    for cache in ("on", "off"):
        cyc[cache], pb[cache] = {}, {}
        for off in (0, 1):
            k = lambda n: f"len{n}/offset{off}/cache_{cache}"   # noqa: E731
            cyc[cache][str(off)] = {str(n): rng([res[k(n)]["mean"] for res in per_place.values() if k(n) in res])
                                    for n in LENS}
            pb[cache][str(off)] = rng([(res[k(1024)]["mean"] - res[k(256)]["mean"]) / 768
                                       for res in per_place.values() if k(1024) in res and k(256) in res])
    return {"cycles": cyc, "per_byte": pb}


def build():
    ads, cls, sizes = crc_tables.kind_tables()
    lib = {}
    for line in open(os.path.join(ROOT, "kinds/crc/configs.txt")):
        f = line.split()
        if f and not f[0].startswith("#"):
            lib[f[0]] = (f[1], f[2])
    recs = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "records/crc/*/*.json"))):
        r = json.load(open(f))
        if r.get("schema") in ("crc-bench/1", "crc-bench/2"):
            recs[(os.path.basename(os.path.dirname(f)), r["adapter"])] = (r, os.path.relpath(f, ROOT))
    bdirs = sorted({b for b, _ in recs}, key=lambda d: next(
        (crc_tables.PAGE_ORDER.index(r["board"]) for (b, _), (r, _) in recs.items() if b == d), 99))
    boards = []
    for d in bdirs:
        r = next(r for (b, _), (r, _) in recs.items() if b == d)
        boards.append(dict({"id": SITE_ID.get(d, d), "records_dir": d, "name": r["board"], "board_decoded": r["board_decoded"], "core": r["core"],
                            "clock_hz": r["clock_hz"], "note_cache_off": crc_tables.before_off(r["board"], r["clock_hz"]),
                            "note_hw_unit": crc_tables.hw_unit_note(r["board"], r["clock_hz"])},
                           **crc_tables.method_of(d, [x for (b, _), (x, _) in recs.items() if b == d])))
    configs, crcs = [], []
    for ad in ads:
        any_rec = next((r for (b, a), (r, _) in recs.items() if a == ad), None)
        if any_rec is None:
            continue
        crcs += [any_rec["crc"]] if any_rec["crc"] not in crcs else []
        c, t = cls.get(ad, (None, None))
        hw = crc_tables.is_hw(cls, ad)
        configs.append(dict({"adapter": ad, "name": any_rec["name"], "lang": LANG[lib[ad][0]],
                             "library": None if hw else lib[ad][1], "crc": any_rec["crc"], "class": c, "table": t,
                             "role": "hardware" if hw else "library"},
                            **({"note": crc_tables.HW_TEXT} if hw else {})))
    configs = [c for c in configs if c["role"] == "library"] + [c for c in configs if c["role"] == "hardware"]
    rows, base = [], {}
    for b in boards:
        for c in configs:
            if (b["records_dir"], c["adapter"]) not in recs:
                continue
            r, path = recs[(b["records_dir"], c["adapter"])]
            core = crc_tables.CORE.get(r["core"].split("(")[-1].rstrip(")"), r["core"])
            tf, ram, code = sizes.get(c["adapter"], (None, None, {}))
            pp = crc_tables.per_place(r)
            row = {"board": b["id"], "adapter": c["adapter"],
                   "flash_bytes": tf + code[core] if tf is not None and core in code else None,
                   "ram_bytes": crc_tables.ram_of(ram, core), "record": path}
            row.update(ranges({p: x["results"] for p, x in pp.items()}))
            rows.append(row)
            if c["role"] == "library":   # the baseline over the libraries' images, as the page shows it beside them
                base.setdefault((b["id"], c["crc"]), {}).update(
                    {(c["adapter"], p): x["baseline"] for p, x in pp.items()})
    baseline = []
    for (bid, crc), per in base.items():
        baseline.append(dict({"board": bid, "crc": crc}, **ranges(per)))
    return {"schema": "crc-data/2",
            "about": ABOUT,
            "source": {"records": "records/crc", "commits": sorted({r["bench_commit"] for r, _ in recs.values()}),
                       "toolchain_image": sorted({r["toolchain_image"] for r, _ in recs.values()})},
            "boards": boards, "crcs": crcs, "configurations": configs, "rows": rows, "baseline": baseline}


def text():
    return json.dumps(build(), indent=1, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        open(OUT, "w").write(text())
    elif sys.argv[1:] == ["--check"]:
        ok = os.path.exists(OUT) and open(OUT).read() == text()
        print(f"site/data/crc.json: {'up to date' if ok else 'not up to date (python3 -I site/crc_data.py --write)'}")
        sys.exit(0 if ok else 1)
    elif not sys.argv[1:]:
        print(text(), end="")
    else:
        sys.exit(__doc__)
