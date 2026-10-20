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
    # the flip-flops of the FPGA start at 0 (the emulator too) : the outputs of the primitives of the stub, which the
    # test-only rewrite does not touch, start at '0' instead of 'U' ; otherwise the first assignment of the PLL
    # (CLKOUT1 <= '0') is an event at time 0 and a process that is sensitive to it runs once more than in the emulator
    stub = re.sub(r"(entity\s+\w+\s+is.*?end entity)", lambda m: re.sub(
        r"\b(O|CLKFBOUT|CLKOUT0|CLKOUT1|LOCKED)(\s*:\s*out std_logic)\b", r"\1\2 := '0'",
        re.sub(r"\b(IO)(\s*:\s*inout std_logic)\b", r"\1\2 := '0'", m.group(1))), stub, flags=re.S | re.I)
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
    raw = lambda p: p.startswith(HERE) or p.endswith("unisim_stub.vhd")
    dfs = []
    user = []
    for lib, path in out:
        if path.endswith("tb_soc.vhd"):     # external names : the front end of the translator does not read them
            continue
        df = frontend.analyze(lib, path)
        if not raw(path):
            frontend.canonicalize(df)       # (the waits of the behavioural PLL cannot be canonicalised either)
            dfs.append(df)
            user.append((lib, path))
    patched = dict(zip([p for l, p in user], [p for l, p in zeroinit.patch(dfs, user, os.path.join(work, "zeroinit"))]))
    test_files = [(lib, path if raw(path) else patched[path]) for lib, path in out]
    # GHDL binds a component to the entity of the same name in the library of the instantiating unit (`work`), the
    # entity FP_UNIT is in `fpu` : the instances are made direct (on the copies in build/)
    for lib, path in test_files:
        if "zeroinit" in path:
            text = open(path, encoding="utf-8", errors="replace").read()
            new = re.sub(r"(\b\w+\s*:\s*)FP_UNIT\b(?!\s*;)", r"\1entity fpu.FP_UNIT", text, flags=re.I)
            if new != text:
                open(path, "w", encoding="utf-8").write(new)
    wd = os.path.join(work, "lib")
    os.makedirs(wd, exist_ok=True)
    for lib, path in test_files:
        run([ghdl, "-a"] + STD + ["--work=" + lib, "--workdir=" + wd, path], wd)
    rom, ext = images(elf)
    write_hex(os.path.join(work, "rom.hex"), rom)
    write_hex(os.path.join(work, "ext.hex"), ext)
    vhd_log = run([ghdl, "--elab-run"] + STD + ["--workdir=" + wd, "-P" + wd, "tb_soc", "--stop-time=%dus" % us], work)
    ghdl_lines = [l.strip() for l in vhd_log.splitlines() if l.startswith("ext ")]
    ghdl_tx = [l.split() for l in vhd_log.splitlines() if l.startswith("tx ")]
    ticks = int(us * 1e6 / 6.95)
    emu = os.path.join(ROOT, "build", "soc63f09")
    c_log = run([emu, "--ext", "0xF00000000:0x10000", "--elf", elf, "--ticks", str(ticks), "--trace-bus"], work)
    c_lines = [re.sub(r"^\s*\d+\s+", "", l).strip() for l in c_log.splitlines() if " ext " in l]
    c_tx = [l.split() for l in c_log.splitlines() if " tx " in l]
    # a pad that nobody drives is 'Z' in VHDL and keeps its pull-up (all ones) in the emulator
    ghdl_lines = [re.sub(r"D=[ZU]+$", lambda m: "D=" + "F" * len(m.group(0)[2:]), l) for l in ghdl_lines]
    n = min(len(ghdl_lines), len(c_lines))
    print("GHDL: %d bus cycles, emulator: %d bus cycles in %d us" % (len(ghdl_lines), len(c_lines), us))
    bus_ok = True
    for i in range(n):
        if ghdl_lines[i] != c_lines[i]:
            print("first difference at cycle %d :" % i)
            for j in range(max(0, i - 3), min(n, i + 3)):
                print("  %s ghdl: %s" % ("*" if j == i else " ", ghdl_lines[j]))
                print("  %s c   : %s" % ("*" if j == i else " ", c_lines[j]))
            bus_ok = False
            break
    if bus_ok:
        print("identical over %d cycles" % n)
    # the transmit lines : same levels, instants within 1 %  (the clock of the bench has a period rounded to the ps)
    # the first entry is the initial value of the line
    g = [(int(t[1]), t[2].strip("'"), t[3].strip("'")) for t in ghdl_tx]
    c = [(int(t[0]) * 6.95, t[2], t[3]) for t in c_tx]
    g = [e for i, e in enumerate(g) if i == 0 or e[1:] != g[i - 1][1:]]
    c = [e for i, e in enumerate(c) if i == 0 or e[1:] != c[i - 1][1:]]
    ok = True
    for i in range(min(len(g), len(c))):
        if g[i][1:] != c[i][1:] or abs(g[i][0] - c[i][0]) > max(2000, 0.01 * g[i][0]):
            print("transmit line differs at change %d : ghdl %s, emulator %s" % (i, g[i], c[i]))
            ok = False
            break
    print("transmit lines: %d changes in GHDL, %d in the emulator%s" % (len(g), len(c), "" if ok else " : DIFFERENT"))
    return 0 if n > 0 and ok and bus_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
