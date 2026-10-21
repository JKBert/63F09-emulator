/* Reads the registers of the bus arbiter (BAC 63F81) and prints them in hexadecimal on ACIA 0. The meaning of the
 * registers is in the header of 63F81.vhd : +0 configuration, +1 current CPU, +2... interrupt masks. */

#include "acia.h"

static void hex(unsigned char v)
{
    static const char digits[] = "0123456789ABCDEF";

    acia_putc(ACIA0_BASE, digits[v >> 4]);
    acia_putc(ACIA0_BASE, digits[v & 15]);
}

int main(void)
{
    unsigned i;

    acia_init(ACIA0_BASE, 12);
    acia_puts(ACIA0_BASE, "BAC:");
    for (i = 0; i < 8; i++)
    {
        acia_putc(ACIA0_BASE, ' ');
        hex(REG8(BAC_BASE + i));
    }
    acia_puts(ACIA0_BASE, "\r\n");
    for (;;)
    {
    }
}
