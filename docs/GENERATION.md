# Generating the C from the VHDL

The emulator is the C translation of the 63F09 VHDL sources, so that it reproduces the hardware
cycle for cycle. The translation is automatic : when the VHDL changes, the C is generated again,
never edited by hand. A few blocks are written by hand because the VHDL only instantiates a vendor
primitive there (see "What is not generated").

The VHDL sources are private and are **never** stored in this repository (`.gitignore` excludes
`*.vhd`, `vhdl/` and `build/`). The generated C is public.

## Overview

    VHDL files ──► GHDL (parse + analysis) ──► typed tree ──► tools/vhdl2c ──► src/gen/*.c, *.h
                       ▲                                           │
        compat rewrites (tools/vhdl2c/compat.py)                   ▼
        sources.list : compilation order                  src/rt (signal kernel) + src/hand
                                                                   │
                                                                   ▼
                                                              the emulator

- **GHDL 4.1.0** (through its library `libghdl` and the Python package `pyGHDL`) parses the VHDL
  and resolves every type and every overloaded call. The translator never parses VHDL itself. GHDL
  is only needed to *generate* ; building the emulator from the committed C needs a C compiler only.
- **tools/vhdl2c** walks the typed tree and writes C (POSIX C99, Allman style).
- **src/rt** is the small C kernel that gives the generated code the VHDL signal semantics
  (current and next values, delta cycles, sensitivity).

## Prerequisites

| Need | Why |
|---|---|
| A C99 compiler (`cc`) | the emulator |
| `git`, `python3` (with `venv`), `make` | the tools |
| GNAT (`gnat`), `zlib1g-dev` | to build GHDL once (`apt-get install gnat make zlib1g-dev`) |
| The VHDL files | any directory ; passed as `VHDL_DIR` |

## One command per task

    make tools                          # builds GHDL 4.1.0 into build/ghdl-install, creates build/venv
    VHDL_DIR=/path/to/vhdl make census  # lists the VHDL constructs and predefined functions used
    VHDL_DIR=/path/to/vhdl make test    # compares the C to GHDL on random stimuli
    make help                           # the whole list

`make tools` is only needed once. The variables `BUILD`, `GHDL_TAG`, `GHDL_SRC`, `GHDL_INSTALL`,
`VENV`, `CC` and `CFLAGS` can be overridden on the command line.

## The source list : `tools/vhdl2c/sources.list`

One line per file, in compilation order : `library logical-name`.

- A logical name such as `63F29` is resolved in `VHDL_DIR` to `63F29.vhd` or `<anything>-63F29.vhd`.
- A name starting with `@` is a path relative to the repository root (used for the declarations
  of the Xilinx primitives, `tests/unisim/unisim_stub.vhd`).
- The libraries are `work`, `fpu` (the FPU package of the core, `library FPU` in the VHDL) and
  `unisim` (the Xilinx primitives). Library names are lower case.

Add a new VHDL file to the design by adding a line here, after the files it depends on.

## Source compatibility rewrites : `tools/vhdl2c/compat.py`

The sources are written for Vivado, which accepts a few constructs that GHDL (like the VHDL-2008
standard) does not. They are rewritten **in a copy** written to `build/vhdl-patched/` ; the files in
`VHDL_DIR` are never modified. Each rewrite keeps the meaning of the construct :

| Construct | Where | Rewrite |
|---|---|---|
| A conditional expression as a port actual (`CE => '1' when C else '0'`) | `61F64x1`, `63F52` | the expression becomes an explicit signal, assigned in a `block` around the instance (an expression used as an actual is an implicit signal, which is what the rewrite writes down) |
| A non-static name in a sensitivity list (`process(BANK_ARRAY(CURRENT_RING)(i), ...)`) | `63F29` | the name is replaced by its longest static prefix (`BANK_ARRAY`), which is what the sensitivity set contains ; the source's own comment relies on that rule |

If a new version of the VHDL brings another construct GHDL rejects, the analysis stops with GHDL's
message : add a rewrite to `PATCHES` for that file.

## Xilinx primitives

`tests/unisim/unisim_stub.vhd` only *declares* the primitives the design instantiates
(`BUFG`, `BUFHCE`, `IOBUF`, `OBUF`, `PLLE2_BASE`, `RAMB18E1`, `RAMB36E1`), so that the analysis
passes. Their behaviour is modelled in C by hand (see below). The declarations were derived from the
generics and ports the sources actually use ; if the VHDL starts using another generic or port, add
it there.

## Signal semantics

VHDL signals are not C variables : a process reads the values the signals had at the start of the
delta cycle and schedules new ones, which all take effect together. The kernel in `src/rt/vsim.c`
implements exactly that :

1. every signal has a current and a next value ;
2. a process reads current values and writes next values ;
3. when the processes of a delta cycle have run, the next values are committed ; the signals that
   changed raise an event, and the processes sensitive to those events run in the next delta cycle ;
4. the simulation is quiescent when a delta commits no change.

Initial values : the logic has two values and a `std_logic` that has no initial value starts at 0, like
a flip-flop of the FPGA (the device is configured with every register at 0). VHDL itself gives `'U'` to
such a signal, and `'U'` is not equal to anything, so a register that is never reset (the clock divider
of the ACIA, written before use) would make GHDL and the C disagree for a while although the hardware is
well defined. The test copies of the sources, written to `build/vhdl-zeroinit/` by `zeroinit.py`, therefore
get an explicit `:= '0'` (or `(others => '0')`) on every signal, variable and entity port of the
`std_logic` family that has none : GHDL then starts like the hardware. The generator never sees those copies.

## What is not generated

Written by hand, because the VHDL only wraps a primitive of the vendor (`RAMB18E1`, `RAMB36E1`,
`PLLE2_BASE`, `BUFG`...) or because they belong to the emulation and not to the hardware :

- the memory blocks and their wrappers (`27F512`, `61F64x1`, `61F512`, `61F32x64`), with configurable
  zones for the ROM and the RAM ;
- the clock generation (`BUFG`, `PLLE2_BASE`) : the emulator is driven by its own tick ;
- the interface of the companion component (Ethernet, PCIe, DDR4...) and the graphic output ;
- the command line (`--ncpus N`, FPU shared or not : the VHDL generics `NCPUS` and `FPU_BY_CORE` stay
  run-time parameters, so the generated code is organised per instance and the `generate`
  statements run when the design is built).

## Checking the result

Every translated block has a test (`tools/vhdl2c/blocktest.py`, run by `make test`). From the ports of
the entity it builds a VHDL test bench and a C test bench that read the same random stimulus file,
apply it phase by phase (clocks low, then clocks high) and print every output after each phase ; GHDL
simulates the VHDL, the generated C is run with the kernel, and the two outputs must be identical.
A block is declared in the `BLOCKS` table of that script : its clocks, its resets, the number of cycles
and the number of warm-up cycles that are not compared. Not only the outputs are compared : every
signal of the block is named in the generated C (`vs_name`) and the test compares them all with the
GHDL VCD trace, phase by phase ; on a difference it reports the first phase and the signals that differ,
which is where to look (`BLOCKTEST_KEEP=<dir>` keeps the traces). The same comparison will serve with
a VCD recorded in Vivado. The tests were checked to fail when the C is deliberately broken.

The final reference is the Vivado simulation : record a VCD of the boot from the ROM and compare it
with the emulator (planned, see the project notes).

## Typical session

    make tools
    export VHDL_DIR=/path/to/vhdl
    make census        # what does the design use, is the translator ready for it ?
    make test          # does the C still match GHDL ?

## Troubleshooting

- *`cannot find "std" library`* : GHDL was not installed in `GHDL_INSTALL` ; run `make tools`.
- *`unit "..." not found in library "fpu"`* : the compilation order in `sources.list` is wrong, or
  the library name is not lower case.
- *A new construct is rejected by GHDL but accepted by Vivado* : see the compatibility rewrites above.
- *`STORAGE_ERROR` inside the translator* : an access to the tree with the wrong kind of node ; run
  `tools/vhdl2c/dump.py <vhdl dir> <unit>` to look at the tree.

## Constructs handled by the translator (reference)

* Types : bits, vectors up to 64 bits in a `uint64_t` and wider ones as `vs_w` (512 bits), integers, enumerations,
  records and arrays (also of vectors : `std_logic_matrix`). Bounds that depend on a generic are computed with
  the largest value of the generic (`GENERIC_MAX` in `gen.py` : NCPUS is 8) ; the generic itself keeps its
  run-time value. Constants and functions used in bounds (`log2i`) are evaluated by the interpreter of `vtypes.py`.
* Sub-programs are monomorphised per argument shape. Signals passed as parameters are pointers, or `vs_ref` when
  the actual is a part of a vector.
* `case?` (matching case) with `-` is translated to a chain of masked comparisons.
* Slices whose bounds depend on a generate parameter or a loop variable must have a constant width
  (`X(g*8 to g*8+7)`), except as the operand of a reduction (`or X(0 to g-1)`).
* `rising_edge` / `falling_edge` of a bit of a vector use the value kept before the event (`prev`).
* `HAND_WRITTEN` entities (RAMs, ROM, PLL, buffers) are not translated : their models are in `src/hand`. Of their
  generics only those in `HAND_GENERICS` (the PLL multipliers and dividers) are passed.
* New block tests : `mmu_63f29` (with `generics={"mmu": 1}`) and the directed `acia_tx` (a `script` of input
  changes in `BLOCKS`).
* Number of cores : an entity with a generic `NCPUS`, or whose architecture declares a constant `NCPUS` (SoC09), is
  generated once per number of cores (`<entity>_n1` to `_n8`) with a dispatcher `<entity>_create` that picks the
  variant from the `g_ncpus` argument. The constants `NCPUS` and `FPU_BY_CORE` of such an architecture become
  parameters of the create function.
* The analyser replaces static expressions by their value (`NCPUS - 1` in a generic map or a range) and keeps what was
  written as the *origin* of the literal. The translator uses the origin when it can translate it.
* Static `if generate` conditions (on NCPUS) are decided when the variant is generated : the branches that do not
  exist in the variant are not translated.
* `inout` ports connected to a part of a vector are tied in both directions.
* Hand-written models of the vendor primitives : IOBUF, OBUF, OBUFT, BUFG, BUFHCE, BUFGCE, PLLE2_BASE ; of the memories :
  RAM_61F64x1, RAM_61F512, RAM_61F32x64, ROM_27F512 (their content is reachable by the loader through
  `vs_region_find`).

## Memory map

`tools/vhdl2c/memmap.py` (run by `make gen` after the translation) reads the address decoding of the SoC (the process
that sets `CS(MUX_...)` from `A`) and writes `src/gen/memmap.h` (`MM_<block>_BASE`, `MM_<block>_SIZE`, used by `src/soc`)
and `docs/MEMORY_MAP.md`. When the blocks move in the VHDL, `make gen` is all it takes.
