"""Checks of the reference (step 1 of the plan), inside the toolchain image.

For the reference as built (build/host/ref_check) and for four builds with one
parameter wrong (build/host/ref_check_wrong1..4, ref_crc.c REF_WRONG):
  check     the catalogue's check value of "123456789"
  residue   the catalogue's residue after a codeword
  python    a second, independent implementation on random messages:
            zlib.crc32 for CRC-32/ISO-HDLC, binascii.crc_hqx(data, 0xFFFF)
            for CRC-16/IBM-3740 (crc_hqx is the CRC with polynomial 0x1021,
            no reflection and no final XOR, from the given initial value).
            Python's standard library has no CRC-8; for CRC-8/SMBUS this
            check is "n/a".
Exit 0 if the reference passes every check and every wrong build is caught
by at least one check for every CRC.
"""
import binascii
import subprocess
import sys
import zlib

WRONG = {1: "polynomial", 2: "initial value", 3: "reflection", 4: "final XOR"}
CRCS = ["CRC-32/ISO-HDLC", "CRC-16/IBM-3740", "CRC-8/SMBUS"]


def second(name, data):
    if name == "CRC-32/ISO-HDLC":
        return zlib.crc32(data)
    if name == "CRC-16/IBM-3740":
        return binascii.crc_hqx(data, 0xFFFF)
    return None


def run(binary):
    res = {c: {} for c in CRCS}
    for line in subprocess.run([binary, "self"], check=True, capture_output=True, text=True).stdout.splitlines():
        name, what, _got, _want, verdict = line.split()
        res[name][what] = verdict == "pass"
    out = subprocess.run([binary, "random", "2000"], check=True, capture_output=True, text=True).stdout
    agree = {c: True for c in CRCS}
    count = {c: 0 for c in CRCS}
    for line in out.splitlines():
        name, hexdata, crc = line.split()
        data = b"" if hexdata == "-" else bytes.fromhex(hexdata)
        want = second(name, data)
        if want is None:
            continue
        count[name] += 1
        if int(crc, 16) != want:
            agree[name] = False
    for c in CRCS:
        res[c]["python"] = agree[c] if second(c, b"") is not None else None
    return res, count


def cell(v):
    return "n/a" if v is None else ("pass" if v else "FAIL")


def main():
    ok = True
    builds = [("reference as built", "build/host/ref_check", None)] + [
        (f"wrong {WRONG[k]}", f"build/host/ref_check_wrong{k}", k) for k in WRONG]
    print(f"{'build':<26} {'CRC':<17} {'check':<6} {'residue':<8} {'python':<6} verdict")
    for label, binary, k in builds:
        res, count = run(binary)
        for c in CRCS:
            r = res[c]
            vals = [r["check"], r["residue"], r["python"]]
            if k is None:
                good = all(v is not False for v in vals)
                verdict = "as expected (passes)" if good else "NOT AS EXPECTED"
            else:
                good = any(v is False for v in vals)
                verdict = "caught" if good else "NOT CAUGHT"
            ok &= good
            print(f"{label:<26} {c:<17} {cell(r['check']):<6} {cell(r['residue']):<8} {cell(r['python']):<6} {verdict}")
        if k is None:
            print(f"(python: {count['CRC-32/ISO-HDLC']} messages for CRC-32, {count['CRC-16/IBM-3740']} for CRC-16; "
                  "every length 0 to 63, then random lengths to 511)")
    print("exit 0: every verdict as expected" if ok else "exit 1: a verdict not as expected")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
