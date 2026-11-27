#!/usr/bin/env python3
"""A test of the pools kind's record path without a board (as
kinds/crc/bench/test_crcrecords.py):
1. run-pools.py's decode() against bench/main.c's struct results: a host
   program built from the struct's own lines (cut out of main.c, so the test
   follows the file) fills every word with its own number and writes the
   block; decode() must put each statistic under its scenario, operation,
   cache state and library, and the words after the libraries in place;
2. poolrecords.py on run files made up here (all numbers are test values,
   not measurements), in a temporary directory: it must take the whole set
   and refuse each broken one, including runs without the board's option
   registers.

Usage: python3 -I test_poolrecords.py      exit 0: every case as expected
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)
COMMIT = "0123456789ab"


SCEN = ("pair", "pair_full", "fill_drain_lifo", "fill_drain_fifo", "mixed", "empty")
OPTIONS = {"schema": "board-options/1", "board": "stm32g474", "chip": "STM32G474RE", "time": "2026-01-01T00:00:00Z",
           "probe_rs": "test", "regions": [{"name": "FLASH_OPTR", "address": "0x40022020", "source": "test",
                                            "words": ["0xfbeff8aa"]}]}


def run_file(place, p):
    stat = {"min": 10, "max": 12, "mean": 10.5, "first": 12, "count": 256}
    res = {f"{s}/{o}/cache_{c}": stat for c in ("off", "on") for s in SCEN for o in ("alloc", "free")}
    res.update({f"init/cache_{c}": stat for c in ("off", "on")})
    return {"schema": "pools-bench-run/1", "result_version": 1, "time": f"2026-01-01T00:{place:02d}:0{p}Z", "host": "test",
            "board": "NUCLEO-G474RE", "core": "Cortex-M4F", "board_id": 3, "board_decoded": "test", "code_location": "flash",
            "kind": "pools", "bench_commit": COMMIT, "toolchain_image": "test:1",
            "adapter": "adapter_test", "lang": "c", "name": "test", "place": place,
            "slot": {"segment": 200, "offset": 4096 * (1 + place), "slot_bytes": 12288},
            "image_base": f"{0x08001000 + 4096 * place:#010x}", "image_bytes": 1000, "fw_sha256": f"elf{place}",
            "image_sha256": f"img{place}", "fixed_sha256": "fixed", "boot_image_sha256": "boot", "bundle": 50,
            "bundle_sha256": "bundle", "far_bytes": 6144, "layout": "fixed, placement, adapter, far, library",
            "run_number": f"{place * 16 + p:#010x}", "pass": p, "attempt": 1, "wait_s": 5.0, "seconds": 5.5,
            "probe_rs": "test", "clock_hz": 170000000, "runs": 256, "blocks": 32, "block_size": 32,
            "sizes": {"code_bytes": 100, "const_bytes": 0, "flash_bytes": 100, "ram_bytes": 1068, "ram_overhead_bytes": 12},
            "overhead_subtracted": 2, "empty_call_raw_min": 8,
            "libs": [{"name": "baseline", "results": res, "errors": 0}, {"name": "test", "results": res, "errors": 0}]}


def case(name, change, expect_rc, expect_text, records, options=OPTIONS):
    with tempfile.TemporaryDirectory() as d:
        runs, out = os.path.join(d, "runs"), os.path.join(d, "records")
        os.makedirs(runs)
        files = {(pl, p): run_file(pl, p) for pl in PLACES for p in (1, 2)}
        built = {"board": "stm32g474", "kind": "pools", "bench_commit": COMMIT, "toolchain_image": "test:1",
                 "toolchain": {"test": 1}, "libs_pinned": ["test"]}
        change(files, built)
        if options is not None:
            with open(os.path.join(runs, "options.json"), "w") as fh:
                json.dump(options, fh)
        with open(os.path.join(runs, "build.json"), "w") as fh:
            json.dump(built, fh)
        for (pl, p), r in files.items():
            if r is not None:
                with open(os.path.join(runs, f"adapter_test-p{pl}-pass{p}.json"), "w") as fh:
                    json.dump(r, fh)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "poolrecords.py"), "--out", out, runs],
                           capture_output=True, text=True)
        made = sorted(os.path.relpath(os.path.join(a, f), out) for a, _, fs in os.walk(out) for f in fs)
        ok = r.returncode == expect_rc and expect_text in r.stdout and len(made) == records
        if ok and records:
            rec = json.load(open(os.path.join(out, made[0])))
            ok = (made == ["stm32g474/adapter_test.json"] and rec["schema"] == "pools-bench/1" and rec["passes"] == 2
                  and rec["option_registers"] == [OPTIONS] and rec["blocks"] == 32 and rec["sizes"]["ram_overhead_bytes"] == 12
                  and [im["place"] for im in rec["images"]] == list(PLACES)
                  and all(len(im["runs"]) == 2 and im["runs"][0]["pass"] == 1 for im in rec["images"])
                  and rec["layout"] == "fixed, placement, adapter, far, library" and rec["toolchain"] == {"test": 1})
        print(f"{'ok  ' if ok else 'FAIL'} {name}: rc {r.returncode}, {len(made)} records; {r.stdout.strip().splitlines()[-1]}")
        if not ok:
            print("     " + r.stdout.replace("\n", "\n     ") + r.stderr)
        return ok


def set_(key, value, at=(12, 2)):
    def f(files, built):
        files[at][key] = value
    return f


def decode_case():
    """decode() against main.c's struct results, word by word."""
    src = open(os.path.join(HERE, "main.c")).read()
    a = src.index("struct stat {")
    b = src.index("volatile struct results results;")
    structs = src[a:b].replace('__attribute__((section(".results")))', "")
    prog = ("#include <stdint.h>\n#include <stdio.h>\n#include <stddef.h>\n#define NSC 6u\n#define NOP 2u\n"
            + structs + "struct results results;\n"
            "int main(void) { uint32_t *w = (uint32_t *)&results; size_t n = sizeof results / 4;\n"
            "  for (size_t i = 0; i < n; i++) w[i] = (uint32_t)(1000 + i);\n"
            "  results.magic = 0x564C5031u; results.version = 1; results.nsc = 6; results.nlibs = 2;\n"
            "  results.blocks = 32; results.block_size = 32;\n"
            "  for (int k = 0; k < 2; k++) {\n"
            "    results.lib[k].s[1][2][1].count = 7; results.lib[k].s[1][2][1].sum = 7 * (100 + k);\n"
            "    results.lib[k].s[1][2][1].min = 90 + k;\n"
            "    results.lib[k].init[0].count = 1; results.lib[k].init[0].sum = 555 + k; results.lib[k].errors = 40 + k; }\n"
            "  results.read_overhead = 2; results.dwt_stalls = 0; results.nonce = 0xabcd;\n"
            "  for (size_t i = 0; i < n; i++) printf(\"%08x\\n\", w[i]); return 0; }\n")
    spec = importlib.util.spec_from_file_location("run_pools", os.path.join(HERE, "run-pools.py"))
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "t.c"), "w").write(prog)
        subprocess.run(["cc", "-std=c11", "-o", os.path.join(d, "t"), os.path.join(d, "t.c")], check=True)
        words = [int(x, 16) for x in subprocess.run([os.path.join(d, "t")], capture_output=True, text=True, check=True).stdout.split()]
    try:
        rp = importlib.util.module_from_spec(spec)
        import sys as _s
        argv, _s.argv = _s.argv, ["run-pools.py"]
        spec.loader.exec_module(rp)
        _s.argv = argv
        head, libs = rp.decode(words, "test")
        ok = (len(words) == rp.NWORDS and head["nonce"] == 0xabcd and head["overhead"] == 2 and head["blocks"] == 32
              and [lib["errors"] for lib in libs] == [40, 41]
              and [lib["results"]["fill_drain_lifo/free/cache_on"]["mean"] for lib in libs] == [98, 99]
              and [lib["results"]["fill_drain_lifo/free/cache_on"]["min"] for lib in libs] == [88, 89]
              and [lib["results"]["init/cache_off"]["mean"] for lib in libs] == [553, 554]
              and len(libs[0]["results"]) == 2 * 6 * 2 + 2)
        why = f"{len(words)} words, NWORDS {rp.NWORDS}"
    except Exception as e:   # noqa: BLE001  (a failure of the test, reported)
        ok, why = False, f"{type(e).__name__}: {e}"
    print(f"{'ok  ' if ok else 'FAIL'} decode() against main.c's struct results: {why}")
    return ok


def main():
    results = [
        decode_case(),
        case("a whole configuration", lambda f, b: None, 0, "1 records,", 1),
        case("a pass missing", lambda f, b: f.__setitem__((12, 2), None), 1, "placement 12: passes [1] of [1, 2]", 0),
        case("an image differs between passes", set_("image_sha256", "other"), 1, "placement 12: the runs differ in image_sha256", 0),
        case("another layout", set_("layout", "fixed, adapter, far, placement, library"), 1, "the runs differ in layout", 0),
        case("another clock", set_("clock_hz", 16000000), 1, "the runs differ in clock_hz", 0),
        case("an invalid run", set_("invalid", "results differ from the reference (1 calls; baseline 0)"), 1, "not a valid run file", 0),
        case("a placement not in the table", lambda f, b: f[(12, 2)].__setitem__("place", 13), 1, "a placement that is not in the table", 0),
        case("uncommitted changes", lambda f, b: ([r.__setitem__("bench_commit", COMMIT + "+dirty") for r in f.values()],
                                                  b.__setitem__("bench_commit", COMMIT + "+dirty")), 1, "cannot be rebuilt", 0),
        case("a run of another build", set_("bench_commit", "fedcba987654"), 1, "not of the build in", 0),
        case("a run of another toolchain image", set_("toolchain_image", "other:2"), 1, "not of the build in", 0),
        case("a run of another board", set_("board_id", 2), 1, "not of the build in", 0),
        case("a field missing in every run", lambda f, b: [r.pop("layout") for r in f.values()], 1, "a run without layout", 0),
        case("one pass only", lambda f, b: [f.__setitem__(k, None) for k in f if k[1] == 2], 1, "passes [1], a series has [1, 2]", 0),
        case("errors without the invalid mark", lambda f, b: f[(12, 2)]["libs"][0].__setitem__("errors", 3), 1,
             "both without errors", 0),
        case("no option registers", lambda f, b: None, 1, "runs without option registers", 0, options=None),
        case("option registers of another board", lambda f, b: None, 1, "not every option register", 0,
             options=dict(OPTIONS, board="stm32g0b1")),
        case("an option register not read", lambda f, b: None, 1, "not every option register", 0,
             options=dict(OPTIONS, regions=[{"name": "FLASH_OPTR", "address": "0x40022020", "source": "test", "error": "x"}])),
        case("another pool shape", set_("blocks", 16), 1, "the runs differ in blocks", 0),
        case("other sizes in one run", set_("sizes", {"code_bytes": 101, "const_bytes": 0, "flash_bytes": 101,
                                                       "ram_bytes": 1068, "ram_overhead_bytes": 12}), 1, "the runs differ in sizes", 0),
        case("no sizes", lambda f, b: [r.pop("sizes") for r in f.values()], 1, "a run without sizes", 0),
        case("results of another configuration", lambda f, b: f[(12, 2)]["libs"][1].__setitem__("name", "other"), 1,
             "both without errors", 0),
    ]
    print(f"{sum(results)} of {len(results)} cases as expected")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
