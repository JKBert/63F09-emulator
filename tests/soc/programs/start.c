/* Start-up code to adapt to your toolchain. The core reads the 16-bit reset vector at 0xFFFFFFFE and runs at
 * 0xFFFF0000 + vector (the upper 16 bits are always 0xFFFF in 32-bit mode) ; the vectors are in 0xFFFFFFC0 -
 * 0xFFFFFFFF (EIRQ0 at 0xFFC0 ... RESET at 0xFFFE, see the header of 63F09.vhd).
 *
 * `reset` must set the stack (in the internal RAM, 0xFFFC0000 - 0xFFFCFFFF, or in the external memory) and call
 * main. The assembly instruction that loads the stack pointer depends on the port : write it where marked. */

extern int main(void);

void reset(void)
{
    /* TODO: load the stack pointer, e.g. with the top of the internal RAM, 0xFFFD0000 */
    main();
    for (;;)
    {
    }
}

/* The table is filled at link time : if the compiler cannot truncate an address in an initialiser, define the
 * vectors in assembly, or generate the table with the linker script (see soc.ld : the symbol `reset` is placed
 * at the address that the vector must hold). */
extern void reset_vector(void);
