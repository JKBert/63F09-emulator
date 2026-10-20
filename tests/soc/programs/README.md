# Test programs for the emulator

C programs for the 63F09 toolchain. Compile them with your gcc, link with a script like `soc.ld` (code in the ROM at
`0xFFFF0000`, vectors at `0xFFFFFFC0`, reset vector at `0xFFFFFFFE`), and run :

    soc63f09 --elf hello.elf --acia 0 --ticks 3000000000

| Program | What it checks |
| --- | --- |
| `hello.c` | the ACIA transmit path, the console |
| `echo.c` | the ACIA receive path (`echo abc \| soc63f09 --elf echo.elf --acia 0,in=- ...`) |
| `memtest.c` | external memory (EXT0 path) and internal RAM |
| `bacregs.c` | the bus arbiter registers through the bus |
| `ptm.c` | a PTM timer |

`start.c` and `soc.ld` are samples : the instruction that loads the stack pointer and the emission of the reset
vector depend on your port. `soc.h` has the addresses the core sees (32 bits) ; the physical address is `0xF`
followed by them, and the emulator maps ELF addresses below 4 GiB by itself.

Send me the `.elf` files (or tell me what you had to change) and I will run them and compare with the VHDL.
