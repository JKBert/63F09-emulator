# Findings

Problems met while translating and running the design. Each entry says what was observed, how it was checked, and
who has to act. **The emulator reproduces the VHDL** : where a finding concerns the behaviour of the chip, GHDL
and the emulator agree (`make cosim`, `make test`), so the cause is in the VHDL or in what the software expects.

## A. Behaviour of the chip

### A1. ACIA 63F50 : the first character written after the set-up is not transmitted
*Status : observed, identical in GHDL and the emulator ; to examine in the VHDL.*

Program (assembled by hand, `build/acia32.elf` in the work tree) : master reset (`03`), divisor 13, control `15`
(8N1, /16), then three times "wait for TDRE, write a character" with `O`, `K`, `LF`.

* The ACIA takes `O` in the transmit register (`tx_data_reg = 4F`, TDRE falls) ; some 9 us later TDRE rises again
  (the byte went to the shift register) and the program writes `K`.
* TxD does **not** carry a frame for `O` : only the frame of `K` appears, 8.7 us later. The third character was not
  seen either within the 200 us simulated.
* A test of the ACIA alone (`acia_tdre`, one write, status read at several instants) does send the frame. So the loss
  depends on the clock relation between E (about 36 MHz, from the CPU) and SYSCLK (24 MHz) : the transmit state
  machine, driven on the falling edge of E, does not start the frame when the data is handed over at that instant.
* The bit time is `2 * (divisor + 1) * 16` SYSCLK cycles, i.e. `24 MHz / (32 * (divisor + 1))` (53 571 bauds for 13),
  twice the value that the header comment suggests for "divide by 16".

To reproduce : `make cosim VHDL_DIR=... ELF=<elf with the sequence above> US=60` prints the changes of TxD of both
simulators ; `soc63f09 --acia 0,baud=53571 --dump file` gives the internal signals (`soc.acia0.tx_*`).

### A2. SoC09 : `CACHEABLE_EXT` of the AMC is not driven
*Status : read in `SoC.vhd`, to confirm.*

`AMC0` is connected with `CACHEABLE_EXT => CACHEABLE_64`, and `CACHEABLE_64` is declared but never assigned. In the
two-valued simulation it is 0, in a four-valued one it is `'U'`. As `CACHEABLE_INT <= CACHEABLE_EXT` in the
non-cached AMC, the whole external space (EXT0) is non-cacheable, which may or may not be wanted.

### A3. Reset values
*Status : by design, for information.*

The registers that the VHDL never resets start at `'U'` in a simulator and at 0 in an FPGA after configuration. The
emulator, like the FPGA, starts them at 0. A simulator with four values (GHDL without the test rewrite, Vivado) sees
`'U'` instead : the comparisons are made with the initial values forced to 0 (`tools/vhdl2c/zeroinit.py`).
The outputs of the vendor primitives matter too : in the first co-simulation, a PLL output that started at `'U'`
instead of `'0'` made the ACIA divider toggle once more at time 0.

## B. Software and tool chain

### B1. Call frame of the gcc back end (fixed by you)
*Status : found with the first test programs ; fixed in the compiler.*

`acia_init` read its first argument with `LDX 4,U` after `PSHS U ; LEAU ,S` : that is the return address, the
argument is at 8,U (`PSHS U` pushes 4 bytes in 32-bit mode, `JSR` 4 more). The VHDL was right.

### B2. `LDMD` and the first load of S
*Status : for information.*

The header of 63F09.vhd says that MD can only be written after a reset and before the first load of S. The test
sequence given in the conversation (`LDMD #$31 ; PSHS U`) pushes with S uninitialised ; the programs must load S
after `LDMD`, as `crt0` does (`11 3D 11`, then `10 CE ...`).

## C. Files and tools

### C1. Constructs that Vivado accepts and GHDL does not
Conditional expression as a port actual (61F64x1, 63F52) and non-static name in a sensitivity list (63F29) :
rewritten on temporary copies, see `docs/VHDL_CHANGES.md`.

### C2. `DMA_63F44` is an empty shell
The file received declares no behaviour. It is not translated.

### C3. FPU not bound in the GHDL runs
*Status : fixed in the test bench, not a VHDL error.*

The instances `FPU_63F39 : FP_UNIT` of 63F09.vhd and 63F81.vhd are components, and the entity `FP_UNIT` is in the
library `fpu` : GHDL's default binding looks in the library of the design unit (`work`) and leaves them unbound
("is not bound" warnings). Vivado binds them by name. The co-simulation therefore did not execute floating-point code
on the GHDL side until this was corrected (`tests/ghdl/cosim.py`).

### C4. GHDL cannot write a VCD of this design
`--vcd` fails with `CONSTRAINT_ERROR grt-avhpi.adb:593` (the empty `if generate` branches, for one). The internal
signals are compared through the dump of the emulator and VHDL-2008 external names in the test bench.
