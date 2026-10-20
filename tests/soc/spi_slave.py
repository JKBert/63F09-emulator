#!/usr/bin/env python3
"""Hand-assembled test of the SPI master against the slave of the emulator (--spi-slave) : sends 0x5A then 0x3C and
stores the answers at 0xF00001000 (expected A5 then 5A). usage: spi_slave.py OUT.elf [clock divisor]"""
import subprocess
import sys

SPI = 0xFFFEC000


def sta(reg):
    return [0xB7] + list((SPI + reg).to_bytes(4, "big"))


def lda(reg):
    return [0xB6] + list((SPI + reg).to_bytes(4, "big"))


def ldai(v):
    return [0x86, v]


def program(divisor):
    p = [0x11, 0x3D, 0x11, 0x10, 0xCE, 0xFF, 0xFD, 0x00, 0x00]         # LDMD #$11 ; LDS #$FFFD0000
    p += ldai(0x01) + sta(1) + ldai(0) + sta(0) + ldai(divisor) + sta(1)   # clock divisor (16 bits)
    p += ldai(0xFF) + sta(2) + ldai(0xFE) + sta(3)                      # select SS0
    for i, byte in enumerate((0x5A, 0x3C)):
        p += ldai(byte) + sta(0)                                        # transmit
        p += lda(1) + [0x84, 0x80, 0x27, 0xF7]                          # wait for DATA ready
        p += lda(0) + [0xB7, 0x00, 0x00, 0x10, i]                       # store the answer
    p += ldai(0xFF) + sta(3)                                            # deselect
    p += [0x20, 0xFE]
    return p


def main(argv):
    divisor = int(argv[2], 0) if len(argv) > 2 else 2
    code = " ".join("%02X" % b for b in program(divisor))
    subprocess.check_call([sys.executable, __file__.replace("spi_slave.py", "mkelf.py"), argv[1],
                           "0xFFFF0000=" + code, "0xFFFFFFFE=00 00"])


if __name__ == "__main__":
    main(sys.argv)
