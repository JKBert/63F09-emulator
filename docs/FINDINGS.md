# Findings

Problems met while translating and running the design. Each entry says what was observed, how it was checked, and
who has to act. Only open points are kept here. **The emulator reproduces the VHDL** : where a finding concerns the behaviour of the chip, GHDL
and the emulator agree (`make cosim`, `make test`), so the cause is in the VHDL or in what the software expects.

## Summary

| Entry | Subject | Status |
|---|---|---|
| A0c | 63F52 ninth SCLK edge | open, to confirm |
| A1 | 63F50 TDRE / first character lost | open |
| A1b | 63F50 receiver never leaves `start_state` | open |
| A2 | SoC09 `CACHEABLE_EXT` undriven | to confirm |
| A3 | reset values | by design |
| B2 | `LDMD` and the first load of S | for information |
| B3 | interrupt flags of the PIA, ACIA, SPI, TWI generated on E | being corrected |

## A. Behaviour of the chip

### A1. ACIA 63F50 : TDRE rises before the byte is in the shift register, the next write overwrites it
*Status : mechanism found in the signals ; identical in GHDL and the emulator ; to correct in the VHDL.*

With the recompiled `hello`, the line comes out as `ello from the 63F09` : the first character is lost, and so would be
the first character after any idle period. The signals of the ACIA (`soc63f09 --dump`, names `soc.acia0.*`) show why :

    1203840  tx_data_reg = 'H'     (write by the CPU, TDRE falls)
    2333160  txrdy = 1             TDRE rises : the transmitter is in start_state, tx_shift_ctrl = load
    2365920  tx_data_reg = 'e'     the program saw TDRE = 1 and writes the next character
    3682440  txdat falls           the frame that goes out is that of 'e'

The transfer of `tx_data_reg` into the shift register happens one baud-clock step *after* TDRE has been set, so a
program that writes as soon as TDRE is set (the normal way) replaces the byte that is waiting. A 6850 sets TDRE when
the byte has entered the shift register. A fix is to set `status_txr_set` when the register is loaded (or to delay
it by the same step).
A test of the ACIA alone (`acia_tdre`, `acia_tx`), where nothing is written in that window, does send the frame.

Other observations on the same device :

* The bit time is `2 * (divisor + 1) * 16` SYSCLK cycles, i.e. `24 MHz / (32 * (divisor + 1))` (53 571 bauds for 13),
  twice what the header comment suggests for "divide by 16".
* The transmit state machine runs a spurious frame (states 1 to 4) right after the hardware reset is released, and
  the line has a short low pulse at that time (about 0.7 us).

### A1b. ACIA 63F50 : the receiver never leaves `start_state` (inverted test)
*Status : found in the source and checked in GHDL and in the emulator.*

In `acia_rx_state` (line 851 of 63F50.vhd)

    if RX_RST = '0' then
        rx_current_state <= start_state;
    else
        if RxBdEdgeFall = '1' then rx_current_state <= rx_next_state; end if;

the test is inverted : the state is forced to `start_state` as long as the receiver is **not** in reset. The
transmitter's equivalent (`acia_tx_state`) tests `TX_RST = '1'`. Result : no character is ever received, `RDRF` stays
0. The directed test `acia_rx` of this repository (a frame 'a' at the rate of the transmitter, then status reads) shows
`RDRF` = 0 in GHDL as well as in the emulator, at the bit times 112, 224, 448 and 896 cycles. The `echo` program
sends nothing back for the same reason. Fix : `RX_RST = '1'`.

### A0c. 63F52 : the master clocks a ninth rising edge after each byte
*Status : observed on the pins, identical in GHDL and the emulator ; to confirm with a real slave.*

In mode 0 (CPOL = CPHA = 0) SCLK has eight pulses for the byte and then one more rising edge that returns to idle
about two bit times later (the counter `CLK_TOGGLES` goes to `D_IN'length * 2 + 1` = 17). A mode-0 slave counts nine
rising edges, shifts once too many and answers `B4` instead of `5A` to the next byte (the answer to the first byte,
`A5`, is right). Either the extra edge belongs to the design (the last bit is sampled on it) and the slaves must
ignore it, or the master should stop at 16 toggles.

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

### B2. `LDMD` and the first load of S
*Status : for information.*

The header of 63F09.vhd says that MD can only be written after a reset and before the first load of S. The test
sequence given in the conversation (`LDMD #$31 ; PSHS U`) pushes with S uninitialised ; the programs must load S
after `LDMD`, as `crt0` does (`11 3D 11`, then `10 CE ...`).

### B3. The interrupt flags of the other peripherals are still generated on E
*Status : PTM (63F40) and BAC (63F81) fixed by the author ; the other peripherals are being corrected.*

The E clock only runs for bus cycles : a core that loops in its instruction cache makes none, E stops, and whatever is
clocked on `falling_edge(E)` stops with it. A timer interrupt then never wakes the core. `tests/soc/programs/b3_cache_idle.asm`
(`elf/b3_loopA.elf` : `BRA *`, `elf/b3_loopB.elf` : a PTM read in the loop) shows it : the marker counts the interrupts
taken by the handler. With the corrected 63F40 and 63F81 both loops give 0x46 after 12 000 000 ticks on 1, 2, 4 and
8 cores, and the co-simulation is identical to GHDL.

What is left is the same pattern in the other peripherals whose interrupt flag is a register written on E : PIA
(`C1_INPUT`, `C2_INPUT`, `C2_OUTPUT` : `IRQ1` and `IRQ2` are set on `falling_edge(E)` from the C1/C2 edges), ACIA
(`falling_edge(E)` in 23 places of 63F50.vhd, including the status bits that give `IRQ_n`), SPI (63F52) and TWI (63F54).
An edge on C1/C2 or the end of a byte that happens while E is stopped is seen only when E restarts, if the
edge detection (`C1_DEL`, `C1_RISE`...) also runs on E it can miss the edge altogether.

## C. Files and tools

### C1. Constructs that Vivado accepts and GHDL does not
Conditional expression as a port actual (61F64x1, 63F52), non-static name in a sensitivity list (63F29) and an empty
statement `end if;;` (63F40, line 199 of the 2026-10-20 version : GHDL reports "extra ';' ignored" as an error) :
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
