#!/usr/bin/env python3
"""The pins socket : a peer pulls PA0-PA3 of PIA 0 low while the program reads the port back, and sees what the
program drives : usage pins_pia.py EMULATOR WORKDIR."""
import os
import socket
import subprocess
import sys
import time

emu, work = sys.argv[1], sys.argv[2]
os.makedirs(work, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
sock = os.path.join(work, "pins.sock")
elf = os.path.join(work, "pins_pia.elf")
# DDRA = FF, ORA = FF, read the port back (the 63F21 returns the pad for an output bit, see FINDINGS A5), store it at
# 0xF00001000 ; then write 0x3C
code = ("86 00 B7 FF FE F0 01  86 00 B7 FF FE F0 00  86 04 B7 FF FE F0 01  "
        "B6 FF FE F0 00 B7 00 00 10 00  "
        "86 00 B7 FF FE F0 01  86 FF B7 FF FE F0 00  86 04 B7 FF FE F0 01  86 3C B7 FF FE F0 00  20 FE")
subprocess.check_call([sys.executable, os.path.join(here, "mkelf.py"), elf, "0xFFFFF000=11 3D 31 7E 00 00 F1 00",
                       "0xFFFFFFFE=F0 00", "0xF100=" + code])
proc = subprocess.Popen([emu, "--ncpus", "1", "--elf", elf, "--pins", sock + ",wait", "--peek", "0xF00001000:1",
                         "--ticks", "6000000"], stdout=subprocess.PIPE, text=True)
for _ in range(100):
    if os.path.exists(sock):
        break
    time.sleep(0.05)
c = socket.socket(socket.AF_UNIX)
c.connect(sock)
c.sendall(b"watch pia0.pa\n")
for i in range(4):
    c.sendall(b"pia0.pa%d 0\n" % i)
c.settimeout(20)
data = b""
try:
    while True:
        d = c.recv(4096)
        if not d:
            break
        data += d
except socket.timeout:
    pass
out = proc.communicate()[0]
lines = [l.split() for l in data.decode().splitlines()]
level = {}
for t, name, v in lines:
    if name.startswith("pia0.pa"):
        level[int(name[7:])] = int(v)
final = sum(level.get(i, 1) << i for i in range(8))
print("PA seen by the peer at the end: %02X" % final)
# DDRA = 0 : the input bits read the pad, 1111 0000 as the peer pulled PA0-3 low
expected = "F0"
assert "F00001000: " + expected in out, out
assert final == 0x30, final               # then the program drives 0x3C, the peer still holds PA0-3 low
print("pins socket test: ok")
