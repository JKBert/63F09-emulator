/* The system on chip as the emulator builds it : the generated BAC_63F81 (cores, MMUs, caches, FPUs, clocks), the
 * memory zones and the devices on its external bus. The glue that the VHDL files do not contain (address decoding,
 * ROM, RAM, peripherals) is described here. */

#ifndef SOC_H
#define SOC_H

#include <stdint.h>
#include <stdio.h>

#include "acia_63f50.h"
#include "bac_63f81.h"
#include "soc/console.h"
#include "vsim.h"

#define SOC_MAX_ZONES   16
#define SOC_MAX_ACIAS   4

/* Ticks of the simulation : EXTAL (24 MHz) has a period of 6000 ticks, CPUCLK (400 MHz) one of 180 ticks. */
#define SOC_EXTAL_HALF  3000

typedef struct soc_zone
{
    uint64_t    base;
    uint64_t    size;
    int         writable;           /* 0 for a ROM (the loader can still fill it) */
    uint8_t     *data;
} soc_zone;

/* An ACIA on the bus, its serial line goes to the host console. */
typedef struct soc_acia_cfg
{
    uint64_t    base;               /* 4 bytes */
    unsigned    baud;               /* rate of the host side : the program must configure the same in the ACIA */
    FILE        *in;                /* bytes sent to the ACIA (NULL : none) */
    FILE        *out;               /* bytes received from the ACIA (NULL : dropped) */
} soc_acia_cfg;

typedef struct soc_cfg
{
    int         ncpus;              /* 1 to 8 */
    int         fpu_shared;         /* FPU_BY_CORE = false */
    soc_zone    zones[SOC_MAX_ZONES];
    int         nzones;
    soc_acia_cfg acias[SOC_MAX_ACIAS];
    int         nacias;
    uint64_t    bac_base;           /* registers of the bus arbiter, 32 bytes */
    uint64_t    mmu_base;           /* registers of the MMUs, 4 KiB */
    uint64_t    elf_offset;         /* added to the addresses of the ELF segments below 4 GiB (see soc_cfg_default) */
    uint64_t    reset_ticks;        /* RESET_n stays low this long */
    uint64_t    max_ticks;          /* the run stops there (0 : never) */
    int         trace_bus;          /* one line per bus cycle on stdout */
} soc_cfg;

typedef struct soc_acia
{
    acia_63f50  core;
    vs_sig      cs, addr, d_out, irq_n, rxd, txd, dcd_n, cts_n, rts_n, mrdy;
    console     con;
} soc_acia;

typedef struct soc
{
    soc_cfg     cfg;
    vs_kernel   k;
    bac_63f81   bac;
    vs_sig      extal, reset_n, nmi_n, firq_n, irq_n, mrdy, dma_breq_n, halt_n;
    vs_sig      e, e_n, q, ba, bs, rw_n, vma, a, d_in, d_out, eirq_n, fic, cacheable;
    vs_sig      sysclk, cpuclk, memclk, cs, mmu_cs, mmu_mrdy, mux_d_in, mux_d_out, mux_mrdy, bus_master;
    soc_acia    acia[SOC_MAX_ACIAS];
    uint64_t    reads, writes, unmapped;
} soc;

void    soc_cfg_default(soc_cfg *c);

/* Adds a zone ; returns 0 on success. The memory is allocated here. */
int     soc_add_zone(soc_cfg *c, uint64_t base, uint64_t size, int writable);

/* Builds the design. Returns 0 on success. */
int     soc_create(soc *s, const soc_cfg *c);
void    soc_destroy(soc *s);

/* Runs until the time limit, `vs_finished`, or no timer is left. */
void    soc_run(soc *s);

/* Loads the PT_LOAD segments of an ELF file (32 or 64 bits, any byte order) into the zones. Returns 0 on success
 * and prints the reason to stderr otherwise. */
int     soc_load_elf(soc *s, const char *path);

#endif
