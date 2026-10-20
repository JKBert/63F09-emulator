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
| A4 | 63F40 16-bit counter read | open |
| B2 | `LDMD` and the first load of S | for information |
| B3 | stall on a cache line fill after a PTM write | to investigate |

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

### A4. 63F40 : the 16-bit counter is read without the divide-by-8 shift

The latch is never read back : the read registers (63F40.vhd, lines 1166 to 1184) return the **counter** :

    1166   D_OUT <= COUNTER(1)(15 downto 8);        -- address "010", timers 2 and 3 likewise (1174, 1182)
    1168   D_OUT <= COUNTER(1)(7 downto 0);         -- address "011"                          (1176, 1184)

In 16-bit mode `COUNTER` (19 bits) holds the count in bits 18..3 : it is loaded with `LATCH_REGISTER & "000"` (lines 133,
171, 191...) and decremented by 8 per clock. The registers return bits 15..0 of it, i.e. the count multiplied by 8 and
truncated to 16 bits. After a latch of 0x0040 is loaded the counter reads 0x02 / 0x00 (0x0200), not 0x00 / 0x40, and a
latch above 0x1FFF gives a wrong value. The 6840 returns the count itself : bits 18..11 and 10..3 are needed.

The 8-bit (dual) mode is affected too. There `COUNTER` is the high counter in bits 18..11, the low counter in bits 10..3
and the divide-by-8 prescaler in bits 2..0 (lines 565 to 618 : `COUNTER(18 downto 11) <= COUNTER(18 downto 11) - 1`,
`COUNTER(10 downto 0) <= LATCH_REGISTER(7 downto 0) & "000"`). The registers return bits 15..8 and 7..0, which mix the
five low bits of the high counter with the three high bits of the low counter, and the five low bits of the low counter
with the prescaler : neither counter can be read. The emulator reproduces the VHDL.

All three timers are affected : the read registers of timer 1 (lines 1166, 1168), timer 2 (1174, 1176) and timer 3
(1182, 1184) are written the same way, and the `TIMER` procedure is shared. For timer 3 with its prescaler enabled
(`CONTROL_REGISTER(3)(0) = '1'`, `IS_TIMER_3`) the counter is loaded with `LATCH_REGISTER & "111"` and decremented by 1
instead of 8, so bits 2..0 are the prescaler : the count is still in bits 18..3 and the read is wrong in the same way.

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

### B3. Core stalls on an instruction-cache line fill after a PTM write (to investigate)

(An earlier version of this note blamed a two-byte `ANDCC` ; that was wrong : in 32-bit mode `1C FF` is two bytes long
and the next instruction runs normally.) With the program `LDMD #$31 ; LDS #$FFFCFFF0 ; ... ; STA PTM0+0 ; ANDCC #$EF ;
BRA *` at `0xFFFFF000` (timer 1 of PTM 0 started by the last write, interrupts then enabled) the bus stops in the
middle of the fill of the line at `0xFFFFF030` : bytes 0 to 6 are read, byte 7 never is, and E stops. GHDL does the same
(`tests/ghdl/cosim.py`, identical over 63 cycles), so it is in the design, not in the emulator. The same code without
the stall is obtained by reading a PTM register after the write. Not analysed further.

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
