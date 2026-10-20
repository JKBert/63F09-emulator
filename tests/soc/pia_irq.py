#!/usr/bin/env python3
"""PIA 0 interrupt on C1, with the core looping in its instruction cache (no bus cycle, E stopped) : the peer raises C1
three times (the `at` command of the pins socket) and the handler counts the interrupts in the external memory.
usage pia_irq.py EMULATOR WORKDIR NCPUS"""
import os
import socket
import subprocess
import sys
import time

emu, work, ncpus = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(work, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
sock = os.path.join(work, "pia_irq.sock")
elf = os.path.join(work, "pia_irq.elf")
# LDMD, LDS, clear the marker, CRA = 07 (port selected, C1 rising edge, IRQ enabled), unmask IRQ, loop in the cache
main = ("11 3D 31  10 CE FF FC FF F0  86 00 B7 00 00 10 00  86 07 B7 FF FE F0 01  1C EF  20 FE  " + "12 " * 16)
# handler : marker++, read the port (acknowledges the flag), RTI ; vector EIRQ19 = $FFE6
isr = "B6 00 00 10 00 8B 01 B7 00 00 10 00 B6 FF FE F0 00 3B"
subprocess.check_call([sys.executable, os.path.join(here, "mkelf.py"), elf, "0xFFFFF000=" + main, "0xFFFFF200=" + isr,
                       "0xFFFFFFE6=F2 00", "0xFFFFFFFE=F0 00"])
proc = subprocess.Popen([emu, "--ncpus", ncpus, "--elf", elf, "--pins", sock + ",wait", "--peek", "0xF00001000:1",
                         "--ticks", "8000000"], stdout=subprocess.PIPE, text=True)
for _ in range(100):
    if os.path.exists(sock):
        break
    time.sleep(0.05)
c = socket.socket(socket.AF_UNIX)
c.connect(sock)
c.sendall(b"watch zzz\n")
for t in (10000, 20000, 30000):                 # the program has set CRA by about 8 us
    c.sendall(b"at %d pia0.c1 0\nat %d pia0.c1 1\n" % (t, t + 2000))
out = proc.communicate()[0]
count = int(out.split("F00001000:")[1].split()[0], 16)
print("PIA interrupts counted with %s core(s): %d" % (ncpus, count))
assert count >= 1, out
