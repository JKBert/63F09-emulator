#!/bin/sh
# Compares the C translation of CLK_63F75 to GHDL on the same stimuli.
# usage: run_test.sh <path to CLK 63F75 vhdl file> [ghdl binary]
set -e
VHDL=$1
GHDL=${2:-ghdl}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$HERE/../..
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$WORK"
python3 "$HERE/gen_stim.py" 600 7 > stim.txt
"$GHDL" -a --std=08 -frelaxed -fsynopsys "$VHDL" "$HERE/tb_clk.vhd"
"$GHDL" -e --std=08 -frelaxed -fsynopsys tb_clk
"$GHDL" -r --std=08 -frelaxed -fsynopsys tb_clk > /dev/null
${CC:-cc} -std=c99 -Wall -Wextra -O2 -I"$ROOT/src/rt" -I"$HERE" -o tb_c \
    "$HERE/tb_clk.c" "$HERE/ref_clk_63f75.c" "$ROOT/src/rt/vsim.c"
./tb_c stim.txt > c.out
if cmp -s ghdl.out c.out
then
    echo "clk: OK ($(wc -l < c.out) samples identical)"
else
    echo "clk: MISMATCH"
    diff ghdl.out c.out | head -20
    exit 1
fi
