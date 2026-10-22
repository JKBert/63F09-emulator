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
    grep -q 'base=FFFFFFFF8 mask=40 R' "$work/smoke.$n.log"                 # reset vector, high byte
    grep -q 'PA=FFFFFF000 base=FFFFFF000 mask=01 R' "$work/smoke.$n.log"                 # first opcode, from the ROM
    grep -q 'cpu=0 LA=0000F100 PA=F0000F100 base=F0000F100 mask=01 R D=86 D64=--------------86$' "$work/smoke.$n.log"      # LDA # fetched after the jump
    grep -q 'PA=F00000010 base=F00000010 mask=01 W D=55 D64=--------------55$' "$work/smoke.$n.log"   # STA wrote 0x55
    echo "smoke test with $n core(s): ok"
done

# The TWI against an I2C EEPROM on its pins : write 0x3C at 0x10, read it back and store it in the external memory.
python3 "$here/twi_eeprom.py" "$work/twi.elf" 0x3C 3
"$emu" --ncpus 2 --elf "$work/twi.elf" --twi-eeprom 0x50 --peek-eeprom --peek 0xF00001000:1 --ticks 20000000 > "$work/twi.log"
grep -q '^F00001000: 3C' "$work/twi.log"            # the byte that was read back
sed -n '/^eeprom/,$p' "$work/twi.log" | sed -n 3p | grep -q '^3C '    # and is in the EEPROM, at 0x10
echo "TWI / I2C EEPROM test: ok"

# Persistence : the content goes to the file after the write, and is loaded again by the next run.
rm -f "$work/ee.bin"
"$emu" --ncpus 2 --elf "$work/twi.elf" --twi-eeprom 0x50,file="$work/ee.bin" --ticks 20000000 > /dev/null
[ "$(od -An -tx1 -j16 -N1 "$work/ee.bin" | tr -d ' ')" = 3c ]
[ "$(od -An -tx1 -j17 -N1 "$work/ee.bin" | tr -d ' ')" = ff ]
"$emu" --ncpus 1 --elf "$work/smoke.elf" --twi-eeprom 0x50,file="$work/ee.bin" --peek-eeprom --ticks 1000 \
    | sed -n '/^eeprom/,$p' | sed -n 3p | grep -q '^3C '
# Write cycle of 1 ms : the program polls nothing, so the address of the read is refused and nothing comes back
"$emu" --ncpus 2 --elf "$work/twi.elf" --twi-eeprom 0x50,wr=1000000 --peek-eeprom --peek 0xF00001000:1 --ticks 20000000 > "$work/twiwr.log"
! grep -q '^F00001000: 3C' "$work/twiwr.log"
sed -n '/^eeprom/,$p' "$work/twiwr.log" | sed -n 3p | grep -q '^3C '
echo "EEPROM file and write cycle test: ok"

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

# The SPI master against the slave of the emulator : sends 5A then 3C, gets A5 then 5A.
python3 "$here/spi_slave.py" "$work/spi.elf"
"$emu" --ncpus 2 --elf "$work/spi.elf" --spi-slave --peek 0xF00001000:2 --ticks 30000000 > "$work/spi.log"
grep -q '^F00001000: A5 5A' "$work/spi.log"

echo "SPI test: ok"

# An illegal opcode (0x87) ends the simulation (the finish of the VHDL) and the emulator says where.
python3 "$here/mkelf.py" "$work/illegal.elf" "0xFFFFF000=11 3D 31 10 CE FF FC FF F0 12 12 87 12 12" "0xFFFFFFFE=F0 00"
"$emu" --ncpus 2 --elf "$work/illegal.elf" --ticks 0 > "$work/illegal.log" 2>&1
grep -q 'ended by the VHDL (finish)' "$work/illegal.log"
grep -q 'core 0 : PC=FFFFF00C .* opcode=87 .*<- trap' "$work/illegal.log"
echo "illegal instruction test: ok"

# The SPI interrupt (EIRQ13, vector 0xFFDA) while the core loops in its cache, so that E is stopped (docs/NOTES.md) : the master
# sends one byte to the slave of the emulator, the handler reads the answer (it acknowledges) and counts at 0xF00001000.
python3 "$here/mkelf.py" "$work/spiirq.elf" \
    "0xFFFFF000=11 3D 31 10 CE FF FC FF F0 86 00 B7 00 00 10 00 86 01 B7 FF FE C0 01 86 00 B7 FF FE C0 00 86 02 B7 FF FE C0 01 86 20 B7 FF FE C0 01 86 FF B7 FF FE C0 02 86 FE B7 FF FE C0 03 86 5A B7 FF FE C0 00 1C EF 20 FE $PAD" \
    "0xFFFFF200=B6 FF FE C0 00 B6 00 00 10 00 8B 01 B7 00 00 10 00 3B" "0xFFFFFFDA=F2 00" "0xFFFFFFFE=F0 00"
"$emu" --ncpus 1 --elf "$work/spiirq.elf" --spi-slave --peek 0xF00001000:1 --ticks 12000000 > "$work/spiirq.log"
grep -q '^F00001000: 01' "$work/spiirq.log"
echo "SPI interrupt test: ok"

# The same for the TWI (EIRQ12, vector 0xFFD8) : TX IRQ enabled, the START command takes the TX register (the flag TX empty rises)
# while the core loops in its cache ; the handler counts and clears the flag by writing the TX register.
python3 "$here/mkelf.py" "$work/twiirq.elf" \
    "0xFFFFF000=11 3D 31 10 CE FF FC FF F0 86 00 B7 00 00 10 00 86 00 B7 FF FE B0 04 86 03 B7 FF FE B0 05 86 00 B7 FF FE B0 06 86 50 B7 FF FE B0 07 86 10 B7 FF FE B0 00 B7 FF FE B0 02 86 01 B7 FF FE B0 01 1C EF 20 FE $PAD" \
    "0xFFFFF200=B6 00 00 10 00 8B 01 B7 00 00 10 00 B7 FF FE B0 00 3B" "0xFFFFFFD8=F2 00" "0xFFFFFFFE=F0 00"
"$emu" --ncpus 1 --elf "$work/twiirq.elf" --twi-eeprom 0x50 --peek 0xF00001000:1 --ticks 20000000 > "$work/twiirq.log"
grep -q '^F00001000: 01' "$work/twiirq.log"
echo "TWI interrupt test: ok"

# And for the ACIA (EIRQ23, vector 0xFFEE) : transmit interrupt enabled (control 0x35), the handler counts and disables it.
python3 "$here/mkelf.py" "$work/aciairq.elf" \
    "0xFFFFF000=11 3D 31 10 CE FF FC FF F0 86 00 B7 00 00 10 00 86 00 B7 FF FE E0 02 86 0D B7 FF FE E0 03 86 03 B7 FF FE E0 00 86 35 B7 FF FE E0 00 1C EF 20 FE $PAD" \
    "0xFFFFF200=B6 00 00 10 00 8B 01 B7 00 00 10 00 86 15 B7 FF FE E0 00 3B" "0xFFFFFFEE=F2 00" "0xFFFFFFFE=F0 00"
"$emu" --ncpus 1 --elf "$work/aciairq.elf" --peek 0xF00001000:1 --ticks 12000000 > "$work/aciairq.log"
grep -q '^F00001000: 01' "$work/aciairq.log"
echo "ACIA interrupt test: ok"

# PIA 0 interrupt on C1 (EIRQ19) while the core loops in its cache : the peer raises C1 three times, the handler counts.
python3 "$here/pia_irq.py" "$emu" "$work/piairq" 1
python3 "$here/pia_irq.py" "$emu" "$work/piairq" 2

# Snapshots : a run saved at 50 us and restored must continue exactly like the run that was not interrupted.
elf=$here/programs/elf/hello3.elf
"$emu" --ncpus 4 --elf "$elf" --acia 0,baud=107142,out="$work/snap_a.txt" --ticks 200000000 --trace-bus > "$work/snap_a.log" 2>&1
"$emu" --ncpus 4 --elf "$elf" --acia 0,baud=107142,out="$work/snap_x.txt" --ticks 100000000 --save "$work/snap.bin" > /dev/null 2>&1
"$emu" --restore "$work/snap.bin" --acia 0,out="$work/snap_b.txt" --ticks 200000000 --trace-bus > "$work/snap_b.log" 2>&1
awk '$1 > 100000200' "$work/snap_a.log" > "$work/snap_a.tail"
awk '$1 > 100000200' "$work/snap_b.log" > "$work/snap_b.tail"
cmp "$work/snap_a.tail" "$work/snap_b.tail"
test -s "$work/snap_a.tail"
rm -f "$work/snap.bin"
echo "snapshot test: ok"

# Threads : each core is a partition run by a thread of its own ; the bus trace must be that of the single kernel.
elf=$here/programs/elf/hello3.elf
"$emu" --ncpus 2 --elf "$elf" --acia 0,baud=107142,out="$work/thr_a.txt" --ticks 200000000 --trace-bus > "$work/thr_a.log" 2>&1
"$emu" --ncpus 2 --threads 3 --elf "$elf" --acia 0,baud=107142,out="$work/thr_b.txt" --ticks 200000000 --trace-bus > "$work/thr_b.log" 2>&1
cmp "$work/thr_a.log" "$work/thr_b.log"
"$emu" --ncpus 2 --threads 1 --elf "$elf" --acia 0,baud=107142,out="$work/thr_c.txt" --ticks 200000000 --trace-bus > "$work/thr_c.log" 2>&1
cmp "$work/thr_a.log" "$work/thr_c.log"
echo "threads test: ok"

# --ticks 0 : the run has no end ; SIGINT stops it cleanly (exit status 0, the snapshot of --save is written).
rm -f "$work/intr.bin"
"$emu" --ncpus 1 --elf "$here/programs/elf/hello3.elf" --ticks 0 --save "$work/intr.bin" > "$work/intr.log" 2>&1 &
pid=$!
sleep 2
kill -INT "$pid"
wait "$pid"
test -s "$work/intr.bin"
grep -q '^interrupted at' "$work/intr.log"
"$emu" --restore "$work/intr.bin" --ticks 200000000 > /dev/null
rm -f "$work/intr.bin"
echo "interrupt test: ok"
