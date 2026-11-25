#!/usr/bin/env python3
"""A test of crcrecords.py without a board: run files are made up here (all
numbers are test values, not measurements), in a temporary directory, and
the record writer must take the whole set and refuse each broken one.

Usage: python3 -I test_crcrecords.py      exit 0: every case as expected
"""
import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLACES = (0, 4, 8, 12, 16, 20, 24, 28)
COMMIT = "0123456789ab"


def run_file(place, p):
    stat = {"min": 10, "max": 12, "mean": 10.5, "first": 12, "count": 256}
    res = {f"len{n}/offset{o}/cache_{c}": stat for c in ("off", "on") for n in (1, 4, 16, 64, 256, 1024) for o in (0, 1)}
    return {"schema": "crc-bench-run/1", "result_version": 2, "time": f"2026-01-01T00:{place:02d}:0{p}Z", "host": "test",
            "board": "NUCLEO-G474RE", "core": "Cortex-M4F", "board_id": 3, "board_decoded": "test", "code_location": "flash",
            "kind": "crc", "crc": "CRC-32/ISO-HDLC", "bench_commit": COMMIT, "toolchain_image": "test:1",
            "adapter": "adapter_test", "lang": "c", "name": "test", "place": place,
            "slot": {"segment": 100, "offset": 4096 * (1 + place), "slot_bytes": 12288},
            "image_base": f"{0x08001000 + 4096 * place:#010x}", "image_bytes": 1000, "fw_sha256": f"elf{place}",
            "image_sha256": f"img{place}", "fixed_sha256": "fixed", "boot_image_sha256": "boot", "bundle": 50,
            "bundle_sha256": "bundle", "far_bytes": 6144, "layout": "fixed, placement, adapter, far, library",
            "run_number": f"{place * 16 + p:#010x}", "pass": p, "attempt": 1, "wait_s": 5.0, "seconds": 5.5,
            "probe_rs": "test", "clock_hz": 170000000, "runs": 256, "lens": [1, 4, 16, 64, 256, 1024], "offsets": [0, 1],
            "overhead_subtracted": 2, "empty_call_raw_min": 8,
            "libs": [{"name": "baseline", "results": res, "errors": 0}, {"name": "test", "results": res, "errors": 0}]}


def case(name, change, expect_rc, expect_text, records):
    with tempfile.TemporaryDirectory() as d:
        runs, out = os.path.join(d, "runs"), os.path.join(d, "records")
        os.makedirs(runs)
        files = {(pl, p): run_file(pl, p) for pl in PLACES for p in (1, 2)}
        built = {"board": "stm32g474", "kind": "crc", "bench_commit": COMMIT, "toolchain_image": "test:1",
                 "toolchain": {"test": 1}, "libs_pinned": ["test"], "crcany_generated_lock_sha256": "lock"}
        change(files, built)
        with open(os.path.join(runs, "build.json"), "w") as fh:
            json.dump(built, fh)
        for (pl, p), r in files.items():
            if r is not None:
                with open(os.path.join(runs, f"adapter_test-p{pl}-pass{p}.json"), "w") as fh:
                    json.dump(r, fh)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "crcrecords.py"), "--out", out, runs],
                           capture_output=True, text=True)
        made = sorted(os.path.relpath(os.path.join(a, f), out) for a, _, fs in os.walk(out) for f in fs)
        ok = r.returncode == expect_rc and expect_text in r.stdout and len(made) == records
        if ok and records:
            rec = json.load(open(os.path.join(out, made[0])))
            ok = (made == ["stm32g474/adapter_test.json"] and rec["schema"] == "crc-bench/1" and rec["passes"] == 2
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


def main():
    results = [
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
        case("results of another configuration", lambda f, b: f[(12, 2)]["libs"][1].__setitem__("name", "other"), 1,
             "both without errors", 0),
    ]
    print(f"{sum(results)} of {len(results)} cases as expected")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
