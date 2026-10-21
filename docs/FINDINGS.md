# Findings

Problems met while translating and running the design. Each entry says what was observed, how it was checked, and
who has to act. Only open points are kept here (what is settled is in [NOTES.md](NOTES.md)). **The emulator reproduces the VHDL** : where a finding concerns the behaviour of the chip, GHDL
and the emulator agree (`make cosim`, `make test`), so the cause is in the VHDL or in what the software expects.

## Summary

| Entry | Subject | Status |
|---|---|---|
| A2 | SoC09 `CACHEABLE_EXT` undriven | to confirm |
| C2 | `DMA_63F44` is an empty shell | waiting for the file |

## A. Behaviour of the chip

### A2. SoC09 : `CACHEABLE_EXT` of the AMC is not driven
*Status : read in `SoC.vhd`, to confirm.*

`AMC0` is connected with `CACHEABLE_EXT => CACHEABLE_64`, and `CACHEABLE_64` is declared but never assigned. In the
two-valued simulation it is 0, in a four-valued one it is `'U'`. As `CACHEABLE_INT <= CACHEABLE_EXT` in the
non-cached AMC, the whole external space (EXT0) is non-cacheable, which may or may not be wanted.

## C. Files and tools

### C2. `DMA_63F44` is an empty shell
The file received declares no behaviour. It is not translated.
