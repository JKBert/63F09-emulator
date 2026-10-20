/* Writes a line on ACIA 0 and stops. Run with :  soc63f09 --elf hello.elf --acia 0,baud=107142 --ticks 3000000000 */

#include "acia.h"

int main(void)
{
    acia_init(ACIA0_BASE, 13);
    acia_puts(ACIA0_BASE, "Hello from the 63F09\r\n");
    for (;;)
    {
    }
}
