# 63F09 system on chip : emulator

Exact emulator, in POSIX C, of the 63F09 system on chip (63F09 core derived from the 6309 with 32/64-bit modes, FPU
63F39, MMU 63F29, caches and bus 63F41/42/44/81, clock 63F75, peripherals PIA 63F21, PTM 63F40, ACIA 63F50,
SPI 63F52, TWI 63F54, watchdog 63F46, memories).

The emulator is **generated from the VHDL** of the chip, signal for signal, and is checked against GHDL entity by
entity (`make test`). The MMU, the caches and the bus are therefore exact to the cycle. What the VHDL does not
contain (host console, ELF loader, command line, companion interface, graphics) is written by hand.

## Status

| Part | State |
| --- | --- |
| Translator VHDL to C (`tools/vhdl2c`) | working, see `docs/GENERATION.md` |
| Core, FPU, MMU, bus arbiter, ACIA, watchdog, clocks | generated, identical to GHDL on the block tests |
| Caches (DMC), PTM, PIA, SPI, TWI | generated and compiled, not yet checked against GHDL |
| SoC top (`SoC09`, translated), pads, ROM/RAM/external memory from an ELF file | working, smoke-tested on 1 to 8 cores |
| Companion interface (EXT0), graphics output | planned |
| Validation against Vivado traces | planned |

## Build

    make tools                 # GHDL and Python tooling used by the translator (once)
    make gen VHDL_DIR=...      # C from the VHDL (the VHDL is private and is not in this repository)
    make emu                   # build/soc63f09
    make test-soc              # smoke test of the emulator
    make test VHDL_DIR=...     # every generated block against GHDL (long)

The generated C is in `src/gen`, so `make emu` needs neither the VHDL nor GHDL.

## Use

    build/soc63f09 --ncpus 4 --fpu shared --elf prog.elf --acia 0,baud=115200

The number of cores (1 to 8) and the sharing of the FPU are chosen on the command line. The serial lines go to the
console (stdin/stdout), to files or to Unix sockets (`--acia N,socket=PATH`) ; the pins of the PIA, PTM, SPI and
TWI and the interrupt inputs are on another socket (`--pins PATH`). See `docs/EMULATOR.md` for every option.

## Documentation

* `docs/GENERATION.md` : how the C is produced from the VHDL, what is supported, how it is checked.
* `docs/EMULATOR.md` : time, memory map, command line, assumptions.

## Licence

CeCILL v2.1, see `LICENSE`. The VHDL sources of the chip are not part of this repository.
