/* Sample linker script for the emulator : code and constants in the ROM, data and stack in the external memory
 * (a ROM cannot be written ; the loader puts every segment where it is linked). Adapt the names of the sections,
 * and the way the reset vector is emitted, to your toolchain. */

MEMORY
{
    rom     (rx)  : ORIGIN = 0xFFFF0000, LENGTH = 0xFFC0
    vectors (r)   : ORIGIN = 0xFFFFFFC0, LENGTH = 0x40
    intram  (rwx) : ORIGIN = 0xFFFC0000, LENGTH = 0x10000
    extram  (rwx) : ORIGIN = 0x00000000, LENGTH = 0x1000000
}

SECTIONS
{
    .text    : { *(.text*) *(.rodata*) } > rom
    .vectors : { KEEP(*(.vectors)) }     > vectors
    .data    : { *(.data*) }             > extram
    .bss     : { *(.bss*) *(COMMON) }    > extram
}
