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

  The addresses of the blocks decoded by the SoC (ROM, peripherals, MMUs, internal RAM) are in [MEMORY_MAP.md](MEMORY_MAP.md),
  generated from the VHDL by `make gen` ; any other address goes to EXT0, the companion on the 64-bit external bus.

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
  (divider /16 : `24e6 / (16 * (divisor + 1))`, 115384 bauds for a divisor of 12, 0.16 % from the 115200 default of the host side ; 107142 for 13).
* `--trace-bus` prints one line per cycle of the bus, at the fall of E (the pins of the external bus show every cycle,
  the internal ROM, RAM and peripherals included) :

  ```
  722520 ext cpu=0 LA=FFFFFFFE PA=FFFFFFFFE base=FFFFFFFF8 mask=40 R D=00 D64=----------------
  900000 ext cpu=1 LA=0000F100 PA=F0000F100 base=F0000F100 mask=01 R D=86 D64=--------------86
  ```

  `cpu` is the core that owns the bus, `LA` the logical address (32 bits) that this core generates, `PA` the physical
  byte address (36 bits) once the MMU is passed, `base` the address of the 64-bit word and `mask` the byte mask. `D` is
  the byte on the 8-bit 6809 bus (what the memory returns for a read, what the core writes for a write) and `D64` the
  eight lanes of the 64-bit bus, most significant first : the data is always by byte, so only the lanes of `mask` are
  shown and the others are `--`. The addresses go to both buses whatever the target is (it is the chip select that
  tells them apart, and the memory map can change), so `D64` is shown for every cycle : a target that does not drive
  the pins leaves the pull-up, `FF`. The data are sampled
  one CPUCLK after the fall of E, when they are stable ; the time printed is that of the fall.
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
clock stretching. By default there is no write cycle time and no page. `tests/soc/twi_eeprom.py` assembles by hand a program for the TWI
(write a byte, restart, read it back) ; `make test-soc` runs it and `make cosim ELF=... ` compares it with GHDL :
249 identical bus cycles and 178 identical changes of the I2C lines.

Options, after the address and separated by commas : `--twi-eeprom 0x50,file=ee.bin,wr=5000,page=8`.

- `file=PATH` : the 256 bytes are loaded from the file at the start (a missing file leaves the memory erased, 0xFF) and
  written back after each write cycle and at the end, so that the content survives from one run to the next.
- `wr=US` : write cycle in microseconds of simulated time. After the STOP that ends a write, the EEPROM does not
  acknowledge its address for that long (a 24C02 needs 5 ms at most), as the real part does ; software has to poll.
- `page=N` : a sequential write wraps inside a page of N bytes (a power of 2 ; a 24C02 has 8). By default the whole
  memory is one page, which is the behaviour the VHDL model of `tests/ghdl/i2c_eeprom.vhd` has.

`tests/rt/test_eeprom.c` (`make test-rt`) checks the page and the write cycle on the model alone.

## Interrupts while E is stopped

The E clock only runs for bus cycles : a core that loops in its instruction cache makes none. The peripherals therefore
raise their interrupt from CPUCLK or SYSCLK, with the flags crossing to E by toggles. `tests/soc/run.sh` checks it for the
PTM, the PIA (`pia_irq.py`), the SPI, the TWI and the ACIA : the core loops in its cache and the handler counts the
interrupts. `tests/soc/programs/b3_cache_idle.asm` is the minimal program (loops A and B).

## Why a run ends

`--ticks N` stops at N ticks, Ctrl-C (or SIGTERM) stops cleanly, and with `--ticks 0` the run goes on until one of these :

* **an illegal instruction** : the only `finish` of the design is in the CPU (63F09.vhd) : an undefined opcode or post-byte
  sends the state machine to a state that ends the simulation (GHDL stops there too). The emulator says so on stderr
  and shows each core (PC after the opcode, opcode, prefix, next state ; `<- trap` marks the core that fell) :

      the simulation was ended by the VHDL (finish) at 777960 ticks : a core executed an illegal instruction
        core 0 : PC=FFFFF00C (after the opcode) opcode=87 prefix=00 next state=848000   <- trap

  The usual causes are a jump into data, a wrong stack, or a program built for another mode (6309 native or emulation,
  `LDMD`).
* **no event left** : nothing is scheduled any more (not seen with the SoC, the clocks never stop).

The counters (ticks, deltas, accesses) are 64 bits : they do not overflow.

## Environment variables

`VS_STATS=1` prints on stderr, at the end of the run, what the kernel did :

    74933 delta cycles ; processes run: 1532201, sum over the deltas of the busiest partition: 981011
    partition 0 : 394480 processes run
    partition 1 : 763029 processes run
    ...

and, when `--threads` starts the threads, which partitions each thread runs. Partition 0 is the SoC, partition c + 1 the
core c (`docs/THREADS.md`) ; without `--threads` the whole design is one partition. The total divided by the sum of the
busiest partition is the best speed-up that threads can give for that program. The counters work in the sequential
mode, in the partitioned sequential mode (`--threads 1`) and with threads, with the same totals. The number of delta
cycles differs between the sequential and the threaded modes : the threads count a delta for each round of a chain of
ties between partitions, which is not a delta of the simulation. There is no other environment variable.

## Running without a limit

`--ticks N` stops the run after N ticks of simulated time (1 tick = 1/144 ns; the default, 100 000 000, is about 0.7 ms).
`--ticks 0` removes the limit. The run then ends when the program of the model calls `finish`, or when the process
receives SIGINT (Ctrl-C) or SIGTERM: the loop stops, the sockets are closed and removed, the snapshot of `--save` is
written, the counters are printed and the exit status is 0. A second signal kills the process as usual.

## Snapshots

`--save FILE` writes the whole state of the machine when the run ends, `--save-at N` writes it at N ticks (the run goes
on), `--restore FILE` starts from it. A restored run continues exactly like the run that was not interrupted (the
bus trace after the snapshot is identical, `tests/soc/run.sh` checks it). Loading takes 0.05 s with one core and 0.2 s
with eight, whatever the time it took to reach that state.

How it works : every allocation of a run (kernel, instances, models, memories) comes from one arena mapped at a fixed
address (`src/rt/vsim.c`), so the snapshot is the content of the arena (zero pages are not stored) and the pointers
inside stay valid. The executable is linked without PIE (the timers and the processes hold code addresses) and the
snapshot carries a hash of it : **it can only be loaded by the executable that wrote it**, rebuild means making a new
one. The machine (`--ncpus`, `--fpu`, `--ext`, the ACIAs, the EEPROM and SPI slave, the pins) comes from the snapshot ;
the host side is the one of the command line : `--acia N[,in=..][,out=..][,socket=..]`, `--pins`, `--dump`,
`--trace-bus`, `--ticks` (absolute time to stop at). An ACIA or the pins that did not exist when the snapshot was made
cannot be added. Sizes : about 40 MB with one core and 300 MB with eight (the signals of the cores), 4 MB once gzipped.

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
