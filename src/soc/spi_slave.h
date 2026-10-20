/* A SPI slave (mode 0) on the pins of the SPI master, selected by SS0 : it answers each byte with the byte received
 * before it (0xA5 for the first one). tests/ghdl/spi_slave.vhd does the same in VHDL. */

#ifndef SOC_SPI_SLAVE_H
#define SOC_SPI_SLAVE_H

#include "vsim.h"

typedef struct spi_slave
{
    vs_sig      *ss, *sclk, *mosi, *miso;
    unsigned    rx, tx, last, cnt;
    unsigned    bytes;
} spi_slave;

/* `ss` is the vector of the select lines : bit 0 selects this slave. */
void spi_slave_create(vs_kernel *k, spi_slave *s, vs_sig *ss, vs_sig *sclk, vs_sig *mosi, vs_sig *miso);

#endif
