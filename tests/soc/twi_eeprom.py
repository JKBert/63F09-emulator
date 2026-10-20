#!/usr/bin/env python3
"""Hand-assembled test of the TWI : writes 0xA5 at address 0x10 of the I2C EEPROM (7-bit address 0x50), reads it
back with a restart and stores it at 0xF00001000. usage: twi_eeprom.py OUT.elf [value [clock divisor]]"""
import subprocess
import sys

TWI = 0xFFFEB000


def sta(reg):
    return [0xB7] + list((TWI + reg).to_bytes(4, "big"))


def lda(reg):
    return [0xB6] + list((TWI + reg).to_bytes(4, "big"))


def ldai(v):
    return [0x86, v]


def wait(reg, mask, set_):
    # LDA reg ; ANDA #mask ; BEQ/BNE back to the LDA
    return lda(reg) + [0x84, mask, 0x27 if set_ else 0x26, 0xF7]


def program(value, divisor=5):
    p = [0x11, 0x3D, 0x11, 0x10, 0xCE, 0xFF, 0xFD, 0x00, 0x00]         # LDMD #$11 ; LDS #$FFFD0000
    p += ldai(0) + sta(4) + ldai(divisor) + sta(5)                      # clock divisor
    p += ldai(0x50) + sta(7)                                            # address of the slave
    p += ldai(0x10) + sta(0) + ldai(0x01) + sta(1)                      # word address, start (write)
    p += wait(2, 0x40, True)                                            # wait for TX empty
    p += ldai(value) + sta(0) + ldai(0x09) + sta(1)                     # data, start + stop
    p += wait(2, 0x02, False)                                           # wait until not busy
    p += ldai(0x10) + sta(0) + ldai(0x01) + sta(1)                      # word address again
    p += wait(2, 0x40, True)
    p += ldai(0x03) + sta(1)                                            # restart, read, no acknowledge, stop
    p += wait(2, 0x80, True)                                            # wait for DATA ready
    p += lda(0) + [0xB7, 0x00, 0x00, 0x10, 0x00]                        # store it at 0x00001000
    p += [0x20, 0xFE]
    return p


def main(argv):
    value = int(argv[2], 0) if len(argv) > 2 else 0xA5
    divisor = int(argv[3], 0) if len(argv) > 3 else 5
    code = " ".join("%02X" % b for b in program(value, divisor))
    subprocess.check_call([sys.executable, __file__.replace("twi_eeprom.py", "mkelf.py"), argv[1],
                           "0xFFFF0000=" + code, "0xFFFFFFFE=00 00"])


if __name__ == "__main__":
    main(sys.argv)
