/* Echoes what ACIA 0 receives.  echo "abc" | soc63f09 --elf echo.elf --acia 0,baud=53571,in=- --ticks ... */

#include "acia.h"

int main(void)
{
    acia_init(ACIA0_BASE, 13);
    for (;;)
    {
        acia_putc(ACIA0_BASE, (char) acia_getc(ACIA0_BASE));
    }
}
