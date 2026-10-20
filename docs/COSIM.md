# Co-simulation GHDL / emulator of the whole SoC

`make cosim VHDL_DIR=... ELF=prog.elf US=20` runs the VHDL of `SoC09` in GHDL and the generated C in the emulator
on the same program, then compares, cycle by cycle, what the external pins show (address, byte mask, read or
write, data) : the bus of the companion carries every access of the chip, the ones to the internal ROM and RAM
included (the address and the mask are output, the data is not for those).

* `tests/ghdl/tb_soc.vhd` is the test bench : clock (24 MHz, 41.7 ns), reset (ten periods), and a 64 KiB memory on
  the external bus.
* GHDL has no RAMB18E1, RAMB36E1 or PLLE2_BASE. `tests/ghdl/models.vhd` replaces the entities 27F512, 61F64x1
  and 61F32x64 by behavioural models, and `tests/ghdl/pll.vhd` gives the PLL an architecture. They do what the C
  models of `src/hand` do (same ports, same timing), so a difference comes from the translated design and not from
  these parts. The ELF is turned into `rom.hex` and `ext.hex`, read by the models.
* A pad that nobody drives is `Z` in VHDL and keeps its pull-up in the emulator : `Z` is read as all ones.

## Result

The five programs of `tests/soc/programs/elf` (`hello`, `echo`, `memtest`, `bacregs`, `ptm`, compiled with the 63F09
gcc) give identical bus cycles over 1750 to 1760 cycles (about 30 us) : reset vector, `LDMD #$11`, `LDS`, 32-bit
jumps and pushes, calls, the caches, the external bus.

## What the programs do on the VHDL (not on the emulator : both agree)

The programs do not reach the ACIA. In `acia_init` the prologue is `34 00 40 33 E4` (PSHS with two post bytes,
LEAU ,S) followed by `AE 44` (LDX 4,U), expecting the first argument at 4,U. With this VHDL the stack, seen after
the run (`soc63f09 --peek 0xFFFFCFFE0:32`), is

    FFFFCFFE8: FF FC FF F8  FF FF 01 53      saved U, return address
    FFFFCFFF0: FF FE E0 00  00 00 00 0D      the two arguments (0xFFFEE000 and 13)

so `LDX 4,U` loads the return address `0xFFFF0153`, `STA ,X` writes into the ROM, and the program ends at address 0
a little later. For the code to work, the frame would have to be `[saved U][arguments]` (a call that does not push the
return address, or an offset of 8). Either the compiler and the VHDL do not agree on the call frame (what `PSHS`
pushes with the second post byte, 32-bit `JSR`), or the programs were run on a simulator of the instruction set that
differs from the VHDL. The emulator is exact with respect to the VHDL.
