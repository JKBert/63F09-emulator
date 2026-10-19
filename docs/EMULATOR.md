# The emulator

`make emu` builds `build/soc63f09` from the generated C (`src/gen`), the hand-written models (`src/hand`), the
runtime (`src/rt`) and the system on chip (`src/soc`). The generated part is the VHDL of the cores, MMUs, caches,
FPU, bus arbiter and peripherals translated signal for signal (see `GENERATION.md`) : the emulator is cycle exact
for them. Everything outside the VHDL (memories, address decoding, host console, ELF loader) is written by hand.

## Time

The simulation has a time in *ticks*. EXTAL is 24 MHz and has a period of 6000 ticks, so a tick is 1/144 ns.
The PLL (hand-written model of PLLE2_BASE) derives CPUCLK (400 MHz, 180 ticks), SYSCLK (24 MHz) from it, as in the
VHDL generics (`CLKFBOUT_MULT`, `CLKOUTn_DIVIDE`, `DIVCLK_DIVIDE`). `LOCKED` rises after `PLL_LOCK_CYCLES`
(8) CLKIN1 periods : this is a placeholder to check against a Vivado trace.

Between two events nothing is computed : timers (`vs_timer_add`) wake the kernel, which then runs delta cycles
until the design is stable.

## Command line

    soc63f09 [--ncpus N] [--fpu by-core|shared] [--ram BASE:SIZE]... [--rom BASE:SIZE]...
             [--elf FILE] [--elf-offset ADDR] [--acia BASE[,baud=N][,in=F][,out=F]]...
             [--bac-base ADDR] [--mmu-base ADDR] [--ticks N] [--trace-bus]

* `--ncpus` (1 to 8) and `--fpu` (`FPU_BY_CORE`) are run-time generics of the generated design. The types that
  depend on NCPUS are sized for 8, the generics keep the value given here.
* Memory zones are physical, 36-bit addresses. Without MMU the physical address is `0xF` followed by the 32 bits
  of the core : a program linked at 0 runs at `0xF00000000`, the reset vector is read at `0xFFFFFFFFE`.
  Defaults : RAM `0xF00000000:0x10000`, ROM `0xFFFFF0000:0x10000`. Giving a zone replaces the defaults.
* `--elf` loads the `PT_LOAD` segments (ELF32 or ELF64, either byte order) at their physical address, into the
  RAM and ROM zones alike. Addresses below 4 GiB get `--elf-offset` (default `0xF00000000`).
* `--acia BASE,baud=N` puts an ACIA on the bus (4 registers) whose serial line is the host console : bytes read from
  stdin (`in=-`) are sent to RxD as 8N1 frames, frames sent on TxD are written to stdout (`out=-`). A file name
  can replace `-`, `none` disables a direction. `baud` is the rate of the host side, it must be the one the
  program sets in the ACIA : with the /16 divider it is `24e6 / (16 * (divisor + 1))`.
* `--trace-bus` prints every bus cycle.

## What is assumed

The VHDL files describe the chip, not the board. The address decoding is therefore a choice made here and can
change : the registers of the bus arbiter are at `--bac-base` (32 bytes), those of the MMUs at `--mmu-base`
(4 KiB, selected for the current bus master), peripherals at their `--acia` base.

## Test programs

`tests/soc/mkelf.py` writes a small big-endian ELF from hexadecimal bytes :

    python3 tests/soc/mkelf.py prog.elf "0xFFFFF000=7E F1 00" "0xFFFFFFFE=F0 00" "0xF100=20 FE"
