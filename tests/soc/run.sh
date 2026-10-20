#!/bin/sh
# Smoke test of the emulator : the reset vector is read from the ROM, the program jumps to the external memory,
# loads A and stores it. The external bus shows every cycle, internal ones included.
# usage: run.sh EMULATOR WORKDIR
set -e
emu=$1
work=$2
here=$(dirname "$0")
mkdir -p "$work"

# 0xFFFFF000 (ROM): JMP $F100 ; 0xF100 (external memory): LDA #$55 ; STA $0010 ; BRA *
python3 "$here/mkelf.py" "$work/smoke.elf" "0xFFFFF000=7E F1 00" "0xFFFFFFFE=F0 00" "0xF100=86 55 B7 00 10 20 FE"
for n in 1 2 4 8
do
    "$emu" --ncpus "$n" --elf "$work/smoke.elf" --ticks 1300000 --trace-bus > "$work/smoke.$n.log"
    grep -q 'A=FFFFFFFF8 mask=40 R' "$work/smoke.$n.log"                 # reset vector, high byte
    grep -q 'A=FFFFFF000 mask=01 R' "$work/smoke.$n.log"                 # first opcode, from the ROM
    grep -q 'A=F0000F100 mask=01 R D=.*86$' "$work/smoke.$n.log"      # LDA # fetched after the jump
    grep -q 'A=F00000010 mask=01 W D=5555555555555555' "$work/smoke.$n.log"   # STA wrote 0x55
    echo "smoke test with $n core(s): ok"
done

# The TWI against an I2C EEPROM on its pins : write 0x3C at 0x10, read it back and store it in the external memory.
python3 "$here/twi_eeprom.py" "$work/twi.elf" 0x3C 1
"$emu" --ncpus 2 --elf "$work/twi.elf" --twi-eeprom 0x50 --peek-eeprom --peek 0xF00001000:1 --ticks 20000000 > "$work/twi.log"
grep -q '^F00001000: 3C' "$work/twi.log"            # the byte that was read back
sed -n '/^eeprom/,$p' "$work/twi.log" | sed -n 3p | grep -q '^3C '    # and is in the EEPROM, at 0x10
echo "TWI / I2C EEPROM test: ok"

# The PIA (6821-like) : select DDRA, all outputs, select ORA, write 0xA5, read ORA and CRA back into the external memory.
python3 "$here/mkelf.py" "$work/pia.elf" "0xFFFFF000=11 3D 31 7E 00 00 F1 00" "0xFFFFFFFE=F0 00" \
    "0xF100=86 00 B7 FF FE F0 01 86 FF B7 FF FE F0 00 86 04 B7 FF FE F0 01 86 A5 B7 FF FE F0 00 B6 FF FE F0 00 B7 00 00 10 00 B6 FF FE F0 01 B7 00 00 10 01 20 FE"
"$emu" --ncpus 2 --elf "$work/pia.elf" --peek 0xF00001000:2 --ticks 3000000 > "$work/pia.log"
grep -q '^F00001000: A5 04' "$work/pia.log"
echo "PIA test: ok"

# The PTM : timer 1 of PTM 0 in continuous mode on SYSCLK, interrupt EIRQ21 (vector 0xFFEA) -> BAC -> core ;
# the handler (ROM 0xFFFFF200) increments a counter in the external memory, acknowledges by reading status and LSB.
PAD="12 12 12 12 12 12 12 12 12 12 12 12 12 12 12 12"
python3 "$here/mkelf.py" "$work/ptmirq.elf" \
    "0xFFFFF000=11 3D 31 10 CE FF FC FF F0 86 00 B7 00 00 10 00 86 01 B7 FF FE D0 01 86 01 B7 FF FE D0 00 86 00 B7 FF FE D0 02 86 04 B7 FF FE D0 03 86 42 B7 FF FE D0 00 1C EF FF 20 FE $PAD" \
    "0xFFFFF200=B6 00 00 10 00 8B 01 B7 00 00 10 00 B6 FF FE D0 01 B6 FF FE D0 03 3B" "0xFFFFFFEA=F2 00" "0xFFFFFFFE=F0 00"
"$emu" --ncpus 1 --elf "$work/ptmirq.elf" --peek 0xF00001000:1 --ticks 12000000 > "$work/ptmirq.log"
! grep -q '^F00001000: 00' "$work/ptmirq.log"       # the handler ran at least once
echo "PTM interrupt test: ok"

# The pins on a Unix socket : a peer pulls PA0-PA3 of PIA 0 low, the program reads them back, the peer sees PA.
python3 "$here/pins_pia.py" "$emu" "$work/pins"

# The SPI master against the slave of the emulator : sends 5A then 3C, gets A5 then B4 (the ninth SCLK edge, FINDINGS A0c).
python3 "$here/spi_slave.py" "$work/spi.elf"
"$emu" --ncpus 2 --elf "$work/spi.elf" --spi-slave --peek 0xF00001000:2 --ticks 30000000 > "$work/spi.log"
grep -q '^F00001000: A5 B4' "$work/spi.log"
echo "SPI test: ok"
