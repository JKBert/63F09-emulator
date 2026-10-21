# Notes

Behaviours of the design and of the tools that are not errors, and what to know about them. Open questions for the
author are in [FINDINGS.md](FINDINGS.md).

## Design

### Reset values
The registers that the VHDL never resets start at `'U'` in a simulator and at 0 in an FPGA after configuration. The
emulator, like the FPGA, starts them at 0. A simulator with four values (GHDL without the test rewrite, Vivado) sees
`'U'` instead : the comparisons are made with the initial values forced to 0 (`tools/vhdl2c/zeroinit.py`).
The outputs of the vendor primitives matter too : in the first co-simulation, a PLL output that started at `'U'`
instead of `'0'` made the ACIA divider toggle once more at time 0.

### `LDMD` and the first load of S
The header of 63F09.vhd says that MD can only be written after a reset and before the first load of S. The test
sequence given in the conversation (`LDMD #$31 ; PSHS U`) pushes with S uninitialised ; the programs must load S
after `LDMD`, as `crt0` does (`11 3D 11`, then `10 CE ...`).

## Tools

### Constructs that Vivado accepts and GHDL does not
Conditional expression as a port actual (61F64x1, 63F52), non-static name in a sensitivity list (63F29) and an empty
statement `end if;;` (63F40, line 199 of the 2026-10-20 version : GHDL reports "extra ';' ignored" as an error) :
rewritten on temporary copies, see `docs/VHDL_CHANGES.md`.

### FPU not bound in the GHDL runs
The instances `FPU_63F39 : FP_UNIT` of 63F09.vhd and 63F81.vhd are components, and the entity `FP_UNIT` is in the
library `fpu` : GHDL's default binding looks in the library of the design unit (`work`) and leaves them unbound
("is not bound" warnings). Vivado binds them by name. The co-simulation therefore did not execute floating-point code
on the GHDL side until this was corrected (`tests/ghdl/cosim.py`).

### GHDL cannot write a VCD of this design
`--vcd` fails with `CONSTRAINT_ERROR grt-avhpi.adb:593` (the empty `if generate` branches, for one). The internal
signals are compared through the dump of the emulator and VHDL-2008 external names in the test bench.
