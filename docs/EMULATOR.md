# The emulator

`make emu` builds `build/soc63f09` from the generated C (`src/gen`), the hand-written models (`src/hand`), the
runtime (`src/rt`) and the host side (`src/soc`). The generated part is the VHDL of the chip translated signal for
signal, **including the top level `SoC09`** : cores, MMUs, caches, FPUs, bus arbiter, address decoding, ROM,
internal RAM and peripherals. It is cycle exact. What is written by hand is what surrounds the pins of SoC09 : the
clock, the reset, the serial lines, the companion memory and the ELF loader.

## Time

The simulation has a time in *ticks*. EXTAL is 24 MHz and has a period of 6000 ticks, so a tick is 1/144 ns.
The PLL (hand-written model of PLLE2_BASE) derives CPUCLK (400 MHz, 180 ticks) and SYSCLK (24 MHz) from it, as in
the VHDL generics (`CLKFBOUT_MULT`, `CLKOUTn_DIVIDE`, `DIVCLK_DIVIDE`). `LOCKED` rises after `PLL_LOCK_CYCLES`
(8) CLKIN1 periods : this is a placeholder to check against a Vivado trace.

Between two events nothing is computed : timers (`vs_timer_add`) wake the kernel, which then runs delta cycles
until the design is stable. RESET_n is released after ten EXTAL periods.

## Command line

    soc63f09 [--ncpus N] [--fpu by-core|shared] [--ext BASE:SIZE]... [--elf FILE] [--elf-offset ADDR]
             [--acia N[,baud=B][,in=F][,out=F]]... [--ticks N] [--dump FILE] [--trace-bus]

* `--ncpus` (1 to 8, default 2) and `--fpu` (`FPU_BY_CORE`, default `shared`) are `NCPUS` and `FPU_BY_CORE`, which
  are constants in `SoC.vhd`. The generator turns them into parameters of the create function, and generates
  SoC09, BAC and DMC once per number of cores (the sizes of their signals depend on it) ; the right variant is
  chosen when the design is built.
* The memory map is that of `SoC.vhd` (physical, 36 bits) :

  | Range | Device |
  | --- | --- |
  | `FFFFF0000` - `FFFFFFFFF` | ROM 27F512 (vectors in the last 64 bytes) |
  | `FFFFEF000` | PIA (2 bytes each, 5 PIAs) |
  | `FFFFEE000` | ACIA (4 bytes each, 2 ACIAs) |
  | `FFFFED000` | PTM (8 bytes each, 2 PTMs) |
  | `FFFFEC000` | SPI |
  | `FFFFEB000` | TWI |
  | `FFFFEA000` | BAC registers |
  | `FFFFE9000` | watchdog |
  | `FFFFD0000` - `FFFFD7000` | MMU 0 to 7 (one 4 KiB page each) |
  | `FFFFC0000` | internal RAM 61F512 (64 KiB) |
  | anything else | EXT0 : the companion, 64-bit external bus |

  Without MMU the physical address is `0xF` followed by the 32 bits of the core : a program linked at 0 runs at
  `0xF00000000` (external bus) and the reset vector is read at `0xFFFFFFFFE` (ROM).
* `--ext BASE:SIZE` adds a memory to the external bus (default `0xF00000000:0x1000000`). The 64-bit lane of a byte
  is given by `BYTE_MASK`.
* `--elf` loads the `PT_LOAD` segments (ELF32 or ELF64, either byte order) at their physical address : into the
  ROM, the internal RAM or the external memories. Addresses below 4 GiB get `--elf-offset` (default
  `0xF00000000`).
* `--acia N,baud=B` connects the serial line of ACIA N (0 or 1) to the console : bytes read from stdin (`in=-`)
  are sent to RxD as 8N1 frames, frames sent on TxD are written to stdout (`out=-`). A file name can replace `-`,
  `none` disables a direction. `B` is the rate of the host side, it must be the one the program sets in the ACIA
  (divider /16 : `24e6 / (32 * (divisor + 1))`).
* `--trace-bus` prints every cycle seen on the external pins. The address and byte mask are output for the internal
  ROM and RAM too, so it is a trace of the whole bus.
* `--dump FILE` writes every change of every named signal of the design, with its hierarchical name.

## Serial lines on a Unix socket

`--acia N,baud=B,socket=PATH[,wait]` replaces stdin/stdout by a Unix domain socket (stream) on which the emulator
listens : one peer at a time, raw bytes (`socat - UNIX-CONNECT:PATH`, `nc -U PATH`, a script). The frames are 8N1 at
the rate `B`. Without `wait` the emulator runs at once and the peer can connect later (the bytes sent by the chip
before that are dropped) ; with `wait` it blocks until a peer is there. When the peer leaves, the next one is
accepted. The socket file is removed when the emulator ends.

## I2C EEPROM on the TWI

`--twi-eeprom ADDR` puts a 24C02-like EEPROM (256 bytes, 7-bit address ADDR, byte and sequential write, random,
current-address and sequential read) on the SDA and SCL pins, `--peek-eeprom` prints its content at the end. The
model (`src/soc/i2c_eeprom.c`, mirrored in VHDL by `tests/ghdl/i2c_eeprom.vhd`) acts on the edges of SCL, there is no
write cycle time and no clock stretching. `tests/soc/twi_eeprom.py` assembles by hand a program for the TWI
(write a byte, restart, read it back) ; `make test-soc` runs it and `make cosim ELF=... ` compares it with GHDL :
249 identical bus cycles and 178 identical changes of the I2C lines.

## Pins on a Unix socket

`--pins PATH[,wait]` serves the pins of the PIAs, PTMs, SPI, TWI and the interrupt inputs on a Unix domain socket
(one peer at a time ; `wait` blocks until it connects). The protocol is made of text lines :

| Direction | Line | Meaning |
|---|---|---|
| emulator to peer | `<ns> <pin> <0 or 1>` | the pin changed ; at connection the current level of every pin is sent |
| peer to emulator | `<pin> <0, 1 or z>` | drives an input ; on an open-drain pad `0` pulls the line low, `1` or `z` lets it go |
| peer to emulator | `at <ns> <pin> <0, 1 or z>` | the same, at that simulated time in nanoseconds |
| peer to emulator | `watch <prefix>`, `unwatch <prefix>` | restricts the pins reported (default : all) |

The names are `pia<0-4>.pa<0-7>` and `pia<n>.c2` (open drain), `pia<n>.c1` (input), `ptm<0-1>.o<1-3>` (output),
`ptm<n>.c<1-3>` and `ptm<n>.g<1-3>` (inputs, active low like `C_n` and `G_n`), `spi.sclk`, `spi.mosi`, `spi.miso`,
`spi.ss<0-15>`, `twi.sda`, `twi.scl` (open drain), `irq`, `firq`, `nmi` and `eirq<0-7>` (inputs, active low). The time
is the simulated one. The peer is polled every microsecond of simulated time ; when it leaves, its pulls are released.
The peer's pulls are seen by every net tied to the pad, so the wired-AND with the chip's own drive is exact.
`tests/soc/pins_pia.py` is a worked example. The serial lines keep their own sockets (`--acia N,socket=PATH`).

## Pads

An `inout` port is a signal shared by the chip and the host. The IOBUF model drives it when T is 0 ; when T is 1 it
drives a one on a pad marked `wand` (the pads of the peripherals, which are pulled up) and the host pulls bits low
with `vs_pull` : the value of the line is the wired-AND of the drivers, as with an open-drain pad and its pull-up.
The data pins of the external bus are driven by the host on a read. A port connected to a part of a vector is tied in both directions.
The simulation is two-valued : high impedance does not exist, a released pad keeps its last value.

## Test programs

`tests/soc/mkelf.py` writes a small big-endian ELF from hexadecimal bytes, `make test-soc` runs one on 1, 2, 4 and
8 cores :

    python3 tests/soc/mkelf.py prog.elf "0xFFFFF000=7E F1 00" "0xFFFFFFFE=F0 00" "0xF100=20 FE"
