/* The system on chip as the emulator builds it : the generated SoC09 (cores, MMUs, caches, FPUs, clocks, ROM, RAM
 * and peripherals, with the address decoding of the VHDL) and, around its pins, the host : the clock, the reset,
 * the serial lines to the console, and a memory standing for the companion component on the external bus (EXT0). */

#ifndef SOC_H
#define SOC_H

#include <stdint.h>
#include <stdio.h>

#include "soc09.h"
#include "soc/console.h"
#include "soc/i2c_eeprom.h"
#include "soc/pins.h"
#include "soc/spi_slave.h"
#include "vsim.h"

#define SOC_MAX_ZONES   16
#define SOC_NACIA       2

/* Ticks of the simulation : EXTAL (24 MHz) has a period of 6000 ticks, CPUCLK (400 MHz) one of 180 ticks. */
#define SOC_EXTAL_HALF  3000

/* Physical addresses decoded by the SoC itself (SoC.vhd) */
#define SOC_ROM_BASE    UINT64_C(0xFFFFF0000)       /* 64 KiB, vectors in the last 64 bytes */
#define SOC_INTRAM_BASE UINT64_C(0xFFFFC0000)       /* 64 KiB */

/* A memory of the external bus (the companion). */
typedef struct soc_zone
{
    uint64_t    base;
    uint64_t    size;
    uint8_t     *data;
} soc_zone;

typedef struct soc_serial
{
    int         enabled;
    unsigned    baud;               /* rate of the host side : the program must set the same in the ACIA */
    FILE        *in;                /* bytes sent to the ACIA (NULL : none) */
    FILE        *out;               /* bytes received from the ACIA (NULL : dropped) */
    char        socket[108];        /* Unix socket path (empty : none) : replaces in and out */
    int         wait;               /* wait for a peer to connect before the run starts */
} soc_serial;

typedef struct soc_cfg
{
    int         ncpus;              /* 1 to 8 */
    int         threads;            /* 0 : one kernel ; n > 0 : each core has a partition of its own, run by n threads */
    int         fpu_shared;         /* FPU_BY_CORE = false */
    soc_zone    zones[SOC_MAX_ZONES];
    int         nzones;
    soc_serial  serial[SOC_NACIA];
    int         twi_eeprom;         /* an I2C EEPROM on the TWI pins, 0 : none */
    unsigned    twi_eeprom_addr;
    char        pins_socket[108];   /* Unix socket for the pins of the peripherals (empty : none), see pins.h */
    int         pins_wait;
    int         spi_slave;          /* a SPI slave on SS0 */    /* its 7-bit address */
    uint64_t    elf_offset;         /* added to the addresses of the ELF segments below 4 GiB */
    uint64_t    reset_ticks;        /* RESET_n stays low this long */
    uint64_t    max_ticks;          /* the run stops there (0 : never) */
    FILE        *dump;              /* changes of every named signal : "<ticks> <name> <value>" */
    int         trace_bus;          /* one line per cycle of the external bus on stdout */
    char        save_path[256];     /* snapshot written at save_at ticks (0 : when the run ends) */
    uint64_t    save_at;
} soc_cfg;

typedef struct soc
{
    soc_cfg     cfg;
    vs_kernel   k;
    soc09       dut;
    /* pins */
    vs_sig      extal, reset_n, nmi_n, firq_n, irq_n, mrdy, dma_breq_n, halt_n;
    vs_sig      e, ba, bs, rw_n, q, addr, data, ext_eirq_n, cpuclk, sysclk, memclk, fic, vma, byte_mask;
    soc09_pia_port_data_t pia_port_data;
    vs_sig      pia_c1, pia_c2;
    vs_sig      acia_rx, acia_tx, acia_rts_n, acia_cts_n, acia_dcd_n;
    soc09_ptm_o_t ptm_o;
    soc09_ptm_c_n_t ptm_c_n;
    soc09_ptm_g_n_t ptm_g_n;
    vs_sig      spi_miso, spi_mosi, spi_ss, spi_sclk, twi_sda, twi_scl;
    i2c_eeprom  eeprom;
    spi_slave   spi;
    pins        pins;
    console     con[SOC_NACIA];
    vs_sig      con_rx[SOC_NACIA], con_tx[SOC_NACIA];
    uint64_t    reads, writes, unmapped;
} soc;

void    soc_cfg_default(soc_cfg *c);

/* Adds a memory to the external bus ; returns 0 on success. */
int     soc_add_zone(soc_cfg *c, uint64_t base, uint64_t size);

/* Builds the design. Returns 0 on success. */
int     soc_create(soc *s, const soc_cfg *c);
void    soc_destroy(soc *s);

/* Runs until the time limit, `vs_finished`, or no timer is left. */
void    soc_run(soc *s);

/* The byte of the ROM, internal RAM or external memory at a physical address, or NULL. */
uint8_t *soc_byte(soc *s, uint64_t addr);

/* Loads the PT_LOAD segments of an ELF file (32 or 64 bits, any byte order) into the ROM, the internal RAM and the
 * memories of the external bus. Returns 0 on success and prints the reason to stderr otherwise. */
int     soc_load_elf(soc *s, const char *path);

#endif
