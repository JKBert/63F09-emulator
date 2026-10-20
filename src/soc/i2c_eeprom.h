/* A 24C02-like I2C EEPROM on the pins of the TWI : 256 bytes, 7-bit address, byte write and sequential write,
 * random read (word address, restart, read), current-address read, sequential read. The pins are open-drain : the
 * model pulls SDA low (vs_pull) and reads the wired-AND of the lines. It acts on the edges of SCL, there is no
 * notion of time (no write cycle, no clock stretching). tests/ghdl/i2c_eeprom.vhd does the same in VHDL. */

#ifndef SOC_I2C_EEPROM_H
#define SOC_I2C_EEPROM_H

#include "vsim.h"

typedef struct i2c_eeprom
{
    vs_sig      *sda, *scl;
    uint8_t     mem[256];
    unsigned    addr7;
    int         phase;              /* 0 idle, 1 address, 2 word address, 3 write data, 4 read data */
    int         next_phase;
    unsigned    cnt;                /* rising edges of SCL in the current byte */
    unsigned    shift;
    unsigned    ptr;
    unsigned    tx;
    int         master_ack;
    unsigned    starts, stops, reads, writes;
} i2c_eeprom;

void i2c_eeprom_create(vs_kernel *k, i2c_eeprom *e, vs_sig *sda, vs_sig *scl, unsigned addr7);

#endif
