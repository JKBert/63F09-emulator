#!/bin/sh
# Smoke test of the emulator : the reset vector is read, then the program is fetched and executed.
# usage: run.sh EMULATOR WORKDIR
set -e
emu=$1
work=$2
here=$(dirname "$0")
mkdir -p "$work"

# LDA #$55 ; STA $0000 (extended) ; BRA *.  The reset vector F000 sends the core to 0xFFFFF000.
python3 "$here/mkelf.py" "$work/smoke.elf" "0xFFFFF000=7E F1 00" "0xFFFFFFFE=F0 00" "0xF100=86 55 B7 00 10 20 FE"
for n in 1 2 4 8
do
    "$emu" --ncpus "$n" --elf "$work/smoke.elf" --ticks 400000 --trace-bus \
        --ram 0xF00000000:0xE000 --rom 0xFFFFF0000:0x10000 --rom 0xF0000F000:0x1000 > "$work/smoke.$n.log"
    grep -q 'A=FFFFFFFFE R' "$work/smoke.$n.log"          # reset vector, high byte
    grep -q 'A=FFFFFF000 R .* D=7E' "$work/smoke.$n.log"  # first opcode (JMP)
    grep -q 'A=F0000F100 R .* D=86' "$work/smoke.$n.log"  # LDA # fetched after the jump
    grep -q 'A=F00000010 W .* D=55' "$work/smoke.$n.log"  # STA wrote A
    echo "smoke test with $n core(s): ok"
done
