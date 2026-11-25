"""Sizes of the cross builds (cross.sh), as a table separated by tabs.

For every core and optimisation level under the directory given (build/x),
every configuration's ELF is compared with the empty program of the same
build (none.elf) by symbol (`arm-none-eabi-readelf -s`): a symbol the
configuration adds is counted by its ELF type and the section it lies in:
  code   FUNC symbols (in flash)
  table  OBJECT symbols in .rodata or .text (constant data in flash)
  ram    OBJECT symbols in .data or .bss (tables built at run time, state)
Weak and unique symbols (Zephyr's __weak functions, ETL's template tables)
count like the others. The adapter's own descriptor (adapter_*, a constant
struct of ours), main() and its buffer (buf) are not counted. "flash" is the growth of text + data of `size`
against none.elf: what the configuration adds to an image in flash.
Columns: core opt config code table ram flash symbols(name:type:size,...)
"""
import os
import subprocess
import sys


def syms(elf):
    """{(name, kind): size}, kind = "t" code, "r" flash data, "d" RAM data."""
    sec = {}
    for line in subprocess.run(["arm-none-eabi-readelf", "-SW", elf], check=True,
                               capture_output=True, text=True).stdout.splitlines():
        line = line.replace("[ ", "[")
        parts = line.split()
        if parts and parts[0].startswith("[") and parts[0].endswith("]") and parts[0][1:-1].isdigit():
            sec[parts[0][1:-1]] = parts[1]
    res = {}
    for line in subprocess.run(["arm-none-eabi-readelf", "-sW", elf], check=True,
                               capture_output=True, text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].endswith(":"):
            continue
        _num, _value, size, typ, _bind, _vis, ndx, name = parts[:8]
        if typ == "FUNC":
            kind = "t"
        elif typ == "OBJECT":
            sname = sec.get(ndx, "")
            if sname.startswith((".rodata", ".text")):
                kind = "r"
            elif sname.startswith((".data", ".bss")):
                kind = "d"
            else:
                continue
        else:
            continue
        key = (name, kind)
        res[key] = max(res.get(key, 0), int(size, 0))
    return res


def flash(elf):
    out = subprocess.run(["arm-none-eabi-size", "-A", "-d", elf], check=True,
                         capture_output=True, text=True).stdout
    total = 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] in (".text", ".rodata", ".data", ".ARM.exidx", ".init_array", ".fini_array"):
            total += int(parts[1])
    return total


def main():
    root = sys.argv[1]
    print("core\topt\tconfig\tcode\ttable\tram\tflash\tsymbols")
    for core in ("m0plus", "m4", "m7", "m33"):
        for opt in ("Os", "O2"):
            d = os.path.join(root, core, opt)
            base = syms(os.path.join(d, "none.elf"))
            base_flash = flash(os.path.join(d, "none.elf"))
            for f in sorted(os.listdir(d)):
                if not f.endswith(".elf") or f == "none.elf":
                    continue
                cfg = f[:-4]
                s = syms(os.path.join(d, f))
                code = table = ram = 0
                names = []
                for (name, typ), size in sorted(s.items()):
                    if (name, typ) in base or name.startswith("adapter_") or name in ("main", "buf") or size == 0:
                        continue
                    if typ == "t":
                        code += size
                    elif typ == "r":
                        table += size
                    else:
                        ram += size
                    names.append(f"{name}:{typ}:{size}")
                print(f"{core}\t{opt}\t{cfg}\t{code}\t{table}\t{ram}\t{flash(os.path.join(d, f)) - base_flash}\t{','.join(names)}")


if __name__ == "__main__":
    main()
