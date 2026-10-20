/* A 24C02-like I2C EEPROM on the pins of the TWI : 256 bytes, 7-bit address, byte write and sequential write,
 * random read (word address, restart, read), current-address read, sequential read. The pins are open-drain : the
 * model pulls SDA low (vs_pull) and reads the wired-AND of the lines. It acts on the edges of SCL, there is no
 * clock stretching. Options (the VHDL model of tests/ghdl/i2c_eeprom.vhd has none of them, the default is the same) :
 *  - a page size : a sequential write wraps inside the page (24C02 : 8 bytes) instead of going on over the 256 bytes ;
 *  - a write cycle : after a STOP that ends a write, the EEPROM does not acknowledge its address for `write_ticks` ticks of
 *    simulated time (24C02 : 5 ms at most) ;
 *  - a file : the 256 bytes are read from it at the start and written back after each write and at the end. */

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
    vs_kernel   *k;
    unsigned    page;               /* bytes of a page of write, a power of 2 (0 : no page, the whole memory) */
    uint64_t    write_ticks;        /* length of the write cycle (0 : none) */
    uint64_t    busy_until;
    int         written;            /* a byte was written since the last START */
    char        path[256];          /* file that holds the memory ("" : none) ; a host thing, set again after a restore */
} i2c_eeprom;

void i2c_eeprom_create(vs_kernel *k, i2c_eeprom *e, vs_sig *sda, vs_sig *scl, unsigned addr7);

/* Options, to be set right after the creation. `path` is read now if the file exists. */
void i2c_eeprom_options(i2c_eeprom *e, unsigned page, uint64_t write_ticks, const char *path);

/* Writes the memory to the file, if there is one. */
void i2c_eeprom_save(i2c_eeprom *e);

#endif
