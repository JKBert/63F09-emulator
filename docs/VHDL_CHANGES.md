# What was changed in, or added next to, the VHDL

**No VHDL source of the chip was modified.** Everything below happens on temporary copies, or in files that are
part of this project. The sources stay as they are in your tree ; none of them is in this repository.

## 1. Rewrites on temporary copies (`tools/vhdl2c/compat.py`)

GHDL (used to read the VHDL) is stricter than Vivado on a few constructs. The generator analyses a patched copy of
the file, written to `build/`, and never touches the original. Two constructs are concerned.

### a. Conditional expression as a port actual — `61F64x1`, `63F52`

Vivado accepts

    ENARDEN => VALID_ADDR when std_logic_vector(to_unsigned(i, 2)) = ADDRESS(15 downto 14) else '0',

in a port map (61F64x1.vhd, `RAMBLOCK16Kx1`, ports `ENARDEN` and `ENBWREN`, and the equivalent in 63F52.vhd).
This is not VHDL-2008 : an actual is a name or an expression, not a conditional expression. The copy gets, around
the instance, a block that makes the implicit signal explicit :

    RAMBLOCK16Kx1_COND : block
        signal COND_ACTUAL_1 : std_logic;
    begin
        COND_ACTUAL_1 <= VALID_ADDR when std_logic_vector(to_unsigned(i, 2)) = ADDRESS(15 downto 14) else '0';
        RAMBLOCK16Kx1 : RAMB18E1 ... port map (..., ENARDEN => COND_ACTUAL_1, ...);
    end block RAMBLOCK16Kx1_COND;

The meaning is the same (an expression used as an actual is an implicit signal driven by the expression).

If you want GHDL, or any strict tool, to read these two files unchanged, write the block yourself, or put the
conditional assignment in a signal declared before the instance.

### b. Non-static name in a sensitivity list — `63F29`

    process(..., BANK_ARRAY(CURRENT_RING)(i), PAYLOAD_ARRAY(CURRENT_RING)(i), ...)

`CURRENT_RING` is a signal, so the name is not static. By the language, the sensitivity set holds the longest
static prefix of the name : `BANK_ARRAY` (resp. `PAYLOAD_ARRAY`). The copy lists these prefixes. Your own comment
in 63F29.vhd already says that `CURRENT_RING` must also be listed, which it is.

## 2. Test-only rewrite (`tools/vhdl2c/zeroinit.py`)

Only for the comparison with GHDL (`make test`), never for the generator. VHDL gives `'U'` to a `std_logic` with no
initial value, and `'U'` is equal to nothing ; the C model is two-valued and starts everything at 0, like the
flip-flops of the FPGA after configuration. The test copies therefore get `:= '0'` (or `(others => '0')`) on every
signal, variable and port of the std_logic family that has no initial value. Where the design really depends on the
initial value of a register it never resets, the two simulators would otherwise disagree during the first cycles.

## 3. The UNISIM file I created (`tests/unisim/unisim_stub.vhd`)

GHDL has no UNISIM library. This file stands for `UNISIM.vcomponents` : the package `vcomponents` with the
component declarations, then one entity per primitive that the design instantiates. It is used **only to analyse
the design** (the generator needs the component declarations) and to run GHDL in the tests. The emulator does not
use it : the primitives are models written in C (`src/hand`).

| Primitive | Declaration | Behaviour in the VHDL stub | C model (`src/hand`) |
| --- | --- | --- | --- |
| `BUFG` | `I`, `O` | `O <= I` | `bufg` : `O` follows `I` one delta later |
| `BUFHCE` | generic `CE_TYPE`; `I`, `CE`, `O` | `O <= I and ce_latch`, `ce_latch` loaded while `I = '0'` | `bufhce` |
| `IOBUF` | generic `SLEW`; `I`, `IO`, `O`, `T` | `IO <= I when T = '0' else 'Z'`; `O <= IO` | `iobuf` |
| `OBUF` | `I`, `O` | `O <= I` | `obuf` |
| `OBUFT` | generic `SLEW`; `I`, `O`, `T` | `O <= I when T = '0' else 'Z'` | `obuft` |
| `PLLE2_BASE` | the 13 generics of the design, `CLKFBIN`, `CLKIN1`, `PWRDWN`, `RST`, `CLKFBOUT`, `CLKOUT0`, `CLKOUT1`, `LOCKED` | **empty architecture** | `plle2_base` : timed outputs derived from `CLKIN1` |
| `RAMB18E1` | all generics and ports used by 61F64x1 | **empty architecture** | folded into `ram_61f64x1` / `ram_61f512` |
| `RAMB36E1` | all generics and ports used by 27F512 and 61F32x64 | **empty architecture** | folded into `rom_27f512` / `ram_61f32x64` |

The empty architectures mean that the entities which contain a PLL or a block RAM cannot be compared with GHDL
(their outputs would be `'U'`) : this is why 61F64x1, 61F512, 61F32x64, 27F512 and the cores' PLL are `HAND_WRITTEN`
in `gen.py` and are not translated. The generics of the declarations are those of the instances in your files ;
the values of the `INIT_xx` generics of the ROM are not read (the content of the ROM comes from the ELF file).

Real UNISIM behaviour that the models do not have : setup/hold and clock-to-output delays, collisions between the
two ports of a block RAM (the models do not detect them), the exact lock time of the PLL (`PLL_LOCK_CYCLES` is a
placeholder) and high impedance (the simulation is two-valued : a released pad keeps its last value).

## 4. What the generator assumes about the VHDL

* VHDL-2008, analysed with `--std=08 -frelaxed -fsynopsys`.
* `std_logic` is treated as two-valued, initial value 0 (see 2).
* `SoC.vhd` declares `NCPUS` and `FPU_BY_CORE` as constants of the architecture. The generator turns them into
  parameters (`--ncpus`, `--fpu`) ; the VHDL is not edited.
* `DMA_63F44` is an empty shell in the files received and is not translated.
