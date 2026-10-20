#!/usr/bin/env python3
"""Co-simulation of the whole SoC09 : GHDL runs the VHDL, the emulator runs the generated C, on the same program,
and the cycles of the external bus are compared.

usage: cosim.py VHDL_DIR GHDL PROGRAM.elf [microseconds]

The vendor primitives are replaced on the GHDL side by behavioural models (tests/ghdl/models.vhd, pll.vhd) that do
what the C models of src/hand do, so that a difference comes from the translated design. The ELF is converted to the
contents of the ROM (rom.hex) and of the external memory (ext.hex).
"""

import os
import re
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "vhdl2c"))

STD = ["--std=08", "-frelaxed", "-fsynopsys"]
OFFSET = 0xF00000000


def images(elf):
    """(rom, ext) : 64 KiB bytearrays for physical FFFFF0000 and F00000000."""
    d = open(elf, "rb").read()
    big = d[5] == 2
    e = ">" if big else "<"
    phoff, = struct.unpack(e + "I", d[28:32])
    phentsize, phnum = struct.unpack(e + "HH", d[42:46])
    rom = bytearray(b"\xff" * 65536)
    ext = bytearray(65536)
    for i in range(phnum):
        t, off, va, pa, fs, ms, fl, al = struct.unpack(e + "IIIIIIII", d[phoff + i * phentsize: phoff + (i + 1) * phentsize])
        if t != 1:
            continue
        for k in range(ms):
            if off == 0 and off + k < phoff + phnum * phentsize:
                continue
            a = pa + k + OFFSET
            b = d[off + k] if k < fs else 0
            if 0xFFFFF0000 <= a < 0xFFFFF0000 + 65536:
                rom[a - 0xFFFFF0000] = b
            elif OFFSET <= a < OFFSET + 65536:
                ext[a - OFFSET] = b
    return rom, ext


def write_hex(path, data):
    with open(path, "w") as f:
        for b in data:
            f.write("%02X\n" % b)


def run(cmd, cwd, out=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stdout.write("command failed: %s\n%s%s\n" % (" ".join(cmd), r.stdout[-2000:], r.stderr[-2000:]))
        sys.exit(1)
    return r.stdout


def main(argv):
    vhdl_dir, ghdl, elf = argv[1], argv[2], os.path.abspath(argv[3])
    us = int(argv[4]) if len(argv) > 4 else 20
    import frontend
    import zeroinit
    frontend.init()
    listing = os.path.join(ROOT, "tools", "vhdl2c", "sources.list")
    files = frontend.project_files(vhdl_dir, listing)
    work = os.path.join(ROOT, "build", "cosim")
    os.makedirs(work, exist_ok=True)
    # the stub of UNISIM gets a behavioural PLL
    stub = open(os.path.join(ROOT, "tests", "unisim", "unisim_stub.vhd")).read()
    pll = open(os.path.join(HERE, "pll.vhd")).read()
    stub = re.sub(r"architecture stub of PLLE2_BASE is\s*begin\s*end architecture stub;", lambda m: pll, stub)
    stub_path = os.path.join(work, "unisim_stub.vhd")
    open(stub_path, "w").write(stub)
    out = []
    placed = False
    for lib, path in files:
        base = os.path.basename(path)
        if base.endswith("unisim_stub.vhd"):
            out.append((lib, stub_path))
        elif any(n in base for n in ("27F512", "61F64x1", "61F32x64")):
            if not placed:
                out.append(("work", os.path.join(HERE, "models.vhd")))
                placed = True
        else:
            out.append((lib, path))
    out.append(("work", os.path.join(HERE, "tb_soc.vhd")))
    dfs = []
    for lib, path in out:
        df = frontend.analyze(lib, path)
        if lib != "unisim":             # the canonicalisation cannot handle the processes with `wait` of the behavioural PLL
            frontend.canonicalize(df)
        dfs.append(df)
    test_files = zeroinit.patch(dfs, out, os.path.join(work, "zeroinit"))
    wd = os.path.join(work, "lib")
    os.makedirs(wd, exist_ok=True)
    for lib, path in test_files:
        run([ghdl, "-a"] + STD + ["--work=" + lib, "--workdir=" + wd, path], wd)
    rom, ext = images(elf)
    write_hex(os.path.join(work, "rom.hex"), rom)
    write_hex(os.path.join(work, "ext.hex"), ext)
    vhd_log = run([ghdl, "--elab-run"] + STD + ["--workdir=" + wd, "-P" + wd, "tb_soc", "--stop-time=%dus" % us], work)
    ghdl_lines = [l.strip() for l in vhd_log.splitlines() if l.startswith("ext ")]
    ticks = int(us * 1e6 / 6.95)
    emu = os.path.join(ROOT, "build", "soc63f09")
    c_log = run([emu, "--ext", "0xF00000000:0x10000", "--elf", elf, "--ticks", str(ticks), "--trace-bus"], work)
    c_lines = [re.sub(r"^\s*\d+\s+", "", l).strip() for l in c_log.splitlines() if " ext " in l]
    # a pad that nobody drives is 'Z' in VHDL and keeps its pull-up (all ones) in the emulator
    ghdl_lines = [re.sub(r"D=[ZU]+$", lambda m: "D=" + "F" * len(m.group(0)[2:]), l) for l in ghdl_lines]
    n = min(len(ghdl_lines), len(c_lines))
    print("GHDL: %d bus cycles, emulator: %d bus cycles in %d us" % (len(ghdl_lines), len(c_lines), us))
    for i in range(n):
        if ghdl_lines[i] != c_lines[i]:
            print("first difference at cycle %d :" % i)
            for j in range(max(0, i - 3), min(n, i + 3)):
                print("  %s ghdl: %s" % ("*" if j == i else " ", ghdl_lines[j]))
                print("  %s c   : %s" % ("*" if j == i else " ", c_lines[j]))
            return 1
    print("identical over %d cycles" % n)
    return 0 if n > 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
