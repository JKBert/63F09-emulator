#!/bin/sh
# Speed of the emulator : seconds for 300 million ticks (about 0.4 ms of simulated time) of hello.elf on 1 and 2 cores.
# usage: bench.sh EMULATOR
emu=$1
elf=$(dirname "$0")/programs/elf/hello3.elf
for n in 1 2; do
    start=$(date +%s.%N)
    "$emu" --ncpus "$n" --elf "$elf" --ticks 300000000 > /dev/null 2>&1
    end=$(date +%s.%N)
    awk -v s="$start" -v e="$end" -v n="$n" 'BEGIN { t = e - s; printf "%d core(s): %.2f s, %.1f Mticks/s\n", n, t, 300 / t }'
done
