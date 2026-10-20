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
