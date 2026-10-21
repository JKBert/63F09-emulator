/* Starts a timer of PTM 0 and counts what happens : prints the first registers on ACIA 0 before and after a delay.
 * It exercises the PTM, the SYSCLK clock tree and the bus ; the register map is that of the 6840 (63F40.vhd). */

#include "acia.h"

static void hex(unsigned char v)
{
    static const char digits[] = "0123456789ABCDEF";

    acia_putc(ACIA0_BASE, digits[v >> 4]);
    acia_putc(ACIA0_BASE, digits[v & 15]);
}

static void dump(void)
{
    unsigned i;

    for (i = 0; i < 8; i++)
    {
        acia_putc(ACIA0_BASE, ' ');
        hex(REG8(PTM0_BASE + i));
    }
    acia_puts(ACIA0_BASE, "\r\n");
}

int main(void)
{
    volatile unsigned long n;

    acia_init(ACIA0_BASE, 12);
    acia_puts(ACIA0_BASE, "PTM before:");
    dump();
    REG8(PTM0_BASE + 2) = 0x03;     /* latch of timer 1 : high byte then low byte (6840) */
    REG8(PTM0_BASE + 3) = 0xE8;
    REG8(PTM0_BASE + 0) = 0x00;     /* control register 1 (6840 : bit 0 clears the reset) */
    for (n = 0; n < 20000; n++)
    {
    }
    acia_puts(ACIA0_BASE, "PTM after: ");
    dump();
    for (;;)
    {
    }
}
