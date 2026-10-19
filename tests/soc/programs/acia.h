#ifndef ACIA_H
#define ACIA_H

#include "soc.h"

static void acia_init(unsigned long base, unsigned divisor)
{
    ACIA_CONTROL(base) = 0x03;                      /* master reset */
    ACIA_DIV_HI(base) = (unsigned char) (divisor >> 8);
    ACIA_DIV_LO(base) = (unsigned char) divisor;
    ACIA_CONTROL(base) = 0x15;                      /* 8 data bits, 1 stop, no parity, /16 */
}

static void acia_putc(unsigned long base, char c)
{
    while ((ACIA_STATUS(base) & ACIA_TDRE) == 0)
    {
    }
    ACIA_DATA(base) = (unsigned char) c;
}

static void acia_puts(unsigned long base, const char *s)
{
    while (*s != '\0')
    {
        acia_putc(base, *s++);
    }
}

static int acia_getc(unsigned long base)
{
    while ((ACIA_STATUS(base) & ACIA_RDRF) == 0)
    {
    }
    return ACIA_DATA(base);
}

#endif
