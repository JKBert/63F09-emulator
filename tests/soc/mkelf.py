#!/usr/bin/env python3
"""Writes a big-endian ELF32 executable from raw segments : mkelf.py OUT.elf ADDR:FILE|HEXBYTES ...
A segment is given as ADDR:path-of-a-binary-file or ADDR=hex-bytes (spaces allowed). Used to test the loader."""
import struct
import sys


def main(argv):
    out = argv[1]
    segs = []
    for a in argv[2:]:
        if "=" in a:
            addr, hexs = a.split("=", 1)
            data = bytes.fromhex(hexs.replace(" ", ""))
        else:
            addr, path = a.split(":", 1)
            data = open(path, "rb").read()
        segs.append((int(addr, 0), data))
    ehsize, phentsize = 52, 32
    off = ehsize + phentsize * len(segs)
    hdr = b"\x7fELF" + bytes([1, 2, 1, 0]) + bytes(8)
    hdr += struct.pack(">HHIIIIIHHHHHH", 2, 0, 1, segs[0][0], ehsize, 0, 0, ehsize, phentsize, len(segs), 0, 0, 0)
    body = b""
    phs = b""
    for addr, data in segs:
        phs += struct.pack(">IIIIIIII", 1, off + len(body), addr, addr, len(data), len(data), 7, 1)
        body += data
    open(out, "wb").write(hdr + phs + body)


if __name__ == "__main__":
    main(sys.argv)
