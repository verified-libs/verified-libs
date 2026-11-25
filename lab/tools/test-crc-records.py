#!/usr/bin/env python3
"""Helper of lab/tools/test-public-export.sh (the CRC ledger cases); made-up
values only, no measurement.

  test-crc-records.py BUILT_DIR OUT_DIR COMMIT
      two made-up CRC records (etl crc32_t256 and zlib crc32) from the
      checksums of a build of kinds/crc/bench/onebuild.sh (BUILT_DIR is
      kinds/crc/build/v2/<board>), naming COMMIT
  test-crc-records.py --fix HOST_FIXES FILE FROM TO
      add a made-up recorded host fix of FILE (blob FROM -> TO)
"""
import glob
import json
import os
import sys

BOARD_ID = {"nrf5340": 1, "stm32g0b1": 2, "stm32g474": 3, "stm32h723": 4, "samd20": 5, "rp2350": 6}


def records(built, out, commit):
    b = json.load(open(os.path.join(built, "build.json")))
    for adapter in ("adapter_etl_crc32_t256", "adapter_zlib_crc32"):
        ims, man = [], None
        for f in sorted(glob.glob(os.path.join(built, "bundle*.json"))):
            m = json.load(open(f))
            for im in m["images"]:
                if im["adapter"] == adapter:
                    man = m
                    ims.append({"place": im["place"], "image_base": im["base"], "image_sha256": im["image_sha256"],
                                "fw_sha256": im["sha256"]})
        if man is None:
            sys.exit(f"{built}: no images of {adapter}")
        rec = {"schema": "crc-bench/1", "board_id": BOARD_ID[b["board"]], "adapter": adapter, "bench_commit": commit,
               "toolchain_image": b["toolchain_image"], "toolchain": b["toolchain"],
               "fixed_sha256": man["fixed_sha256"], "boot_image_sha256": man["boot_image_sha256"],
               "layout": man.get("layout"), "note": "made up by test-public-export.sh from a build: no measurement",
               "images": sorted(ims, key=lambda i: i["place"])}
        with open(os.path.join(out, adapter + ".json"), "w") as fh:
            json.dump(rec, fh, indent=1)
            fh.write("\n")


def fix(path, file, before, after):
    d = json.load(open(path)) if os.path.exists(path) else {"fixes": []}
    d["fixes"].append({"file": file, "from": before, "to": after, "date": "test", "what": "a test change",
                       "numbers": "none (test)", "control": "none (test)"})
    with open(path, "w") as fh:
        json.dump(d, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 5 and a[0] == "--fix":
        fix(*a[1:])
    elif len(a) == 3:
        records(*a)
    else:
        sys.exit(__doc__)
