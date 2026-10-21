/* Writes patterns in the external memory and in the internal RAM, reads them back, reports on ACIA 0. */

#include "acia.h"

static int check(volatile unsigned char *p, unsigned n)
{
    unsigned i;

    for (i = 0; i < n; i++)
    {
        p[i] = (unsigned char) (i * 7 + 3);
    }
    for (i = 0; i < n; i++)
    {
        if (p[i] != (unsigned char) (i * 7 + 3))
        {
            return 0;
        }
    }
    return 1;
}

int main(void)
{
    acia_init(ACIA0_BASE, 12);
    acia_puts(ACIA0_BASE, "Hello from the 63F09\r\n");
    acia_puts(ACIA0_BASE, check((volatile unsigned char *) 0x00010000UL, 4096) ? "external RAM: ok\r\n" : "external RAM: FAIL\r\n");
    acia_puts(ACIA0_BASE, check((volatile unsigned char *) INTRAM_BASE, 4096) ? "internal RAM: ok\r\n" : "internal RAM: FAIL\r\n");
    for (;;)
    {
    }
}
