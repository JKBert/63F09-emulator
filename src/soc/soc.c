#include <signal.h>
#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"
#include "soc/snapshot.h"

void soc_cfg_default(soc_cfg *c)
{
    memset(c, 0, sizeof(*c));
    c->ncpus = 2;                                   /* NCPUS of SoC.vhd */
    c->fpu_shared = 1;                              /* FPU_BY_CORE = false in SoC.vhd */
    /* A is 36 bits wide. Without MMU the physical address is 0xF followed by the 32 bits of the core, so a program
     * linked at 0x00000000 runs at 0xF00000000 (the external bus), the reset vector is at 0xFFFFFFFFE (the ROM). */
    c->elf_offset = UINT64_C(0xF00000000);
    /* A board holds RESET_n for far longer than the start of the PLL : the peripherals (the ACIA, the PTM...) are
     * reset synchronously on E, which runs only once the PLL has locked. Five microseconds are enough. */
    c->reset_ticks = 720100;                        /* 5 us, and not on an edge of CPUCLK (a race between the simulators) */
}

int soc_add_zone(soc_cfg *c, uint64_t base, uint64_t size)
{
    soc_zone    *z;

    if (c->nzones == SOC_MAX_ZONES || size == 0)
    {
        return -1;
    }
    z = &c->zones[c->nzones];
    z->data = vs_arena_alloc((size_t) size);       /* in the arena, so that a snapshot holds it */
    if (z->data == NULL)
    {
        return -1;
    }
    z->base = base;
    z->size = size;
    c->nzones++;
    return 0;
}

static soc_zone *find_zone(soc_cfg *c, uint64_t addr)
{
    int i;

    for (i = 0; i < c->nzones; i++)
    {
        soc_zone    *z = &c->zones[i];

        if (addr >= z->base && addr - z->base < z->size)
        {
            return z;
        }
    }
    return NULL;
}

#define TRACE_DELAY    360             /* ticks : one CPUCLK */

/* The signal of the design with that hierarchical name, or NULL. */
static vs_sig *find_signal(soc *s, const char *name)
{
    size_t i;

    for (i = 0; i < s->k.nsigs; i++)
    {
        if (s->k.sigs[i]->name != NULL && strcmp(s->k.sigs[i]->name, name) == 0)
        {
            return s->k.sigs[i];
        }
    }
    return NULL;
}

/* The internal signals that --trace-bus shows next to the pins of the external bus. */
static void find_trace_signals(soc *s)
{
    int     i;
    char    name[96];

    s->tr_a = find_signal(s, "soc.a");
    s->tr_d_in = find_signal(s, "soc.d_in");
    s->tr_d_out = find_signal(s, "soc.d_out");
    s->tr_master = find_signal(s, "soc.bus_master");
    for (i = 0; i < s->cfg.ncpus && i < SOC_MAXCPUS; i++)
    {
        snprintf(name, sizeof(name), "soc.bac0.smp.core(%d).dmc.dmc.mmu_with_cache_l1.cpu_a", i);
        s->tr_la[i] = find_signal(s, name);
        if (s->tr_la[i] == NULL && i == 0)          /* a single core has no index */
        {
            s->tr_la[i] = find_signal(s, "soc.bac0.smp.dmc.dmc.mmu_with_cache_l1.cpu_a");
        }
    }
}

/* One line per cycle of the external bus, at the fall of E :
 *   ext cpu=<active core> LA=<logical address of that core, 8 digits> PA=<physical byte address, 9 digits>
 *       base=<address of the 64-bit word> mask=<2> R|W D=<byte of the 6809 bus> D64=<the 8 lanes of the 64-bit bus>
 * The data of the cycle appear on the bus with the fall of E itself, so the line is printed a little later (one
 * CPUCLK), once they are stable ; the addresses are those of the fall. "--" marks the lanes of the 64-bit bus that
 * are not significant (not in the byte mask). The pins of the 64-bit bus carry data only for the external memories :
 * for the ROM, the internal RAM and the peripherals (physical addresses from 0xFFFF00000) D64 is all dashes. */
static void trace_print(vs_kernel *k, void *arg)
{
    soc         *s = arg;
    char        d64[17];
    int         lane;
    vs_sig      *d8 = s->tr_rd ? s->tr_d_out : s->tr_d_in;       /* seen from the memories : d_out leaves them (read) */
    int         internal = s->tr_pa >= UINT64_C(0xFFFF00000);

    (void) k;
    for (lane = 7; lane >= 0; lane--)
    {
        if (((s->tr_mask >> lane) & 1) && !internal)
        {
            snprintf(d64 + 2 * (7 - lane), 3, "%02X", (unsigned) ((s->data.cur >> (8 * lane)) & 0xFF));
        }
        else
        {
            memcpy(d64 + 2 * (7 - lane), "--", 2);
        }
    }
    d64[16] = '\0';
    printf("%12llu ext cpu=%u LA=", (unsigned long long) s->k.now - TRACE_DELAY, s->tr_cpu);
    if (s->tr_la_now != UINT64_MAX)
    {
        printf("%08llX", (unsigned long long) s->tr_la_now);
    }
    else
    {
        printf("--------");
    }
    printf(" PA=%09llX base=%09llX mask=%02X %c D=", (unsigned long long) s->tr_pa,
           (unsigned long long) (s->tr_pa & ~UINT64_C(7)), (unsigned) s->tr_mask, s->tr_rd ? 'R' : 'W');
    if (d8 != NULL)
    {
        printf("%02X", (unsigned) (d8->cur & 0xFF));
    }
    else
    {
        printf("--");
    }
    printf(" D64=%s\n", d64);
}

static void trace_cycle(soc *s, uint64_t mask)
{
    unsigned    cpu = s->tr_master != NULL ? (unsigned) s->tr_master->cur : 0;

    s->tr_cpu = cpu;
    s->tr_pa = s->tr_a != NULL ? s->tr_a->cur : 0;
    s->tr_mask = mask;
    s->tr_rd = (int) s->rw_n.cur;
    s->tr_la_now = cpu < SOC_MAXCPUS && s->tr_la[cpu] != NULL ? s->tr_la[cpu]->cur & 0xFFFFFFFF : UINT64_MAX;
    vs_timer_add(&s->k, s->k.now + TRACE_DELAY, trace_print, s);
}

/* The companion on the external bus : 64-bit data, the lane of the byte is given by BYTE_MASK. A read puts the
 * 8 bytes of the line on DATA while the bus owner reads ; a write is captured when E falls. The pad is driven by
 * the SoC (IOBUF) during a write and by the host otherwise. */
static void companion_run(void *inst)
{
    soc         *s = inst;
    uint64_t    base = s->addr.cur << 3;
    soc_zone    *z = find_zone(&s->cfg, base);
    int         lane;

    if (s->rw_n.cur == 1 && s->vma.cur == 1)
    {
        uint64_t v = 0;

        if (z != NULL)
        {
            for (lane = 0; lane < 8; lane++)
            {
                v |= (uint64_t) z->data[base - z->base + lane] << (8 * lane);
            }
        }
        else
        {
            v = UINT64_MAX;
        }
        vs_drive(&s->data, v);
    }
    else if (s->rw_n.cur == 1)
    {
        vs_drive(&s->data, UINT64_MAX);         /* nothing is read : the pins are pulled up */
    }
    if (vs_falling(&s->e) && s->vma.cur == 1 && s->ba.cur == 0)
    {
        uint64_t mask = s->byte_mask.cur;

        if (s->cfg.trace_bus)
        {
            trace_cycle(s, mask);
        }
        if (s->rw_n.cur == 0)
        {
            s->writes++;
            for (lane = 0; lane < 8; lane++)
            {
                if (((mask >> lane) & 1) && z != NULL)
                {
                    z->data[base - z->base + lane] = (uint8_t) (s->data.cur >> (8 * lane));
                }
            }
            if (z == NULL)
            {
                s->unmapped++;
            }
        }
        else
        {
            s->reads++;
            if (z == NULL)
            {
                s->unmapped++;
            }
        }
    }
}

/* with --trace-bus : the changes of the transmit lines (the VHDL test bench prints the same) */
static void i2c_log(void *inst)
{
    soc *s = inst;

    if (s->cfg.trace_bus)
    {
        printf("%12llu i2c '%d' '%d'\n", (unsigned long long) s->k.now, (int) (s->twi_sda.cur & 1), (int) (s->twi_scl.cur & 1));
    }
}

static void tx_run(void *inst)
{
    soc *s = inst;

    if (s->cfg.trace_bus)
    {
        printf("%12llu tx %d %d\n", (unsigned long long) s->k.now, (int) ((s->acia_tx.cur >> 1) & 1),
               (int) (s->acia_tx.cur & 1));
    }
}

static void reg(soc *s, vs_sig *sig, const char *name, unsigned width, uint64_t init)
{
    vs_register_signal(&s->k, sig, init);
    vs_name(&s->k, sig, "soc", name, width);
}

static void release_reset(vs_kernel *k, void *arg)
{
    (void) k;
    vs_drive(&((soc *) arg)->reset_n, 1);
}

/* The pins of the peripherals on a Unix socket (see pins.h). The vectors declared ascending ("0 to 4", "1 to 3")
 * have their first element in the most significant bit. */
static int pins_setup(soc *s)
{
    char    name[16];
    int     i, k;

    pins_init(&s->pins);
    for (i = 0; i < 5; i++)
    {
        for (k = 0; k < 8; k++)
        {
            snprintf(name, sizeof(name), "pia%d.pa%d", i, k);
            pins_add(&s->pins, name, &s->pia_port_data.a[i], (unsigned) k, PIN_OD);
        }
        snprintf(name, sizeof(name), "pia%d.c1", i);
        pins_add(&s->pins, name, &s->pia_c1, (unsigned) (4 - i), PIN_IN);
        snprintf(name, sizeof(name), "pia%d.c2", i);
        pins_add(&s->pins, name, &s->pia_c2, (unsigned) (4 - i), PIN_OD);
    }
    for (i = 0; i < 2; i++)
    {
        for (k = 1; k <= 3; k++)
        {
            snprintf(name, sizeof(name), "ptm%d.o%d", i, k);
            pins_add(&s->pins, name, &s->ptm_o.a[i], (unsigned) (3 - k), PIN_OUT);
            snprintf(name, sizeof(name), "ptm%d.c%d", i, k);
            pins_add(&s->pins, name, &s->ptm_c_n.a[i], (unsigned) (3 - k), PIN_IN);
            snprintf(name, sizeof(name), "ptm%d.g%d", i, k);
            pins_add(&s->pins, name, &s->ptm_g_n.a[i], (unsigned) (3 - k), PIN_IN);
        }
    }
    pins_add(&s->pins, "spi.sclk", &s->spi_sclk, 0, PIN_OD);
    pins_add(&s->pins, "spi.mosi", &s->spi_mosi, 0, PIN_OD);
    pins_add(&s->pins, "spi.miso", &s->spi_miso, 0, PIN_OD);
    for (k = 0; k < 16; k++)
    {
        snprintf(name, sizeof(name), "spi.ss%d", k);
        pins_add(&s->pins, name, &s->spi_ss, (unsigned) k, PIN_OD);
    }
    pins_add(&s->pins, "twi.sda", &s->twi_sda, 0, PIN_OD);
    pins_add(&s->pins, "twi.scl", &s->twi_scl, 0, PIN_OD);
    pins_add(&s->pins, "irq", &s->irq_n, 0, PIN_IN);
    pins_add(&s->pins, "firq", &s->firq_n, 0, PIN_IN);
    pins_add(&s->pins, "nmi", &s->nmi_n, 0, PIN_IN);
    for (k = 0; k < 8; k++)
    {
        snprintf(name, sizeof(name), "eirq%d", k);
        pins_add(&s->pins, name, &s->ext_eirq_n, (unsigned) k, PIN_IN);
    }
    if (pins_listen(&s->pins, s->cfg.pins_socket, s->cfg.pins_wait) != 0)
    {
        return -1;
    }
    pins_create(&s->k, &s->pins);
    return 0;
}

int soc_create(soc *s, const soc_cfg *c)
{
    vs_sig  *sens[4];
    int     i;

    if (c->ncpus < 1 || c->ncpus > 8)
    {
        fprintf(stderr, "the number of CPUs goes from 1 to 8\n");
        return -1;
    }
    s->cfg = *c;
    s->reads = s->writes = s->unmapped = 0;
    vs_kernel_init(&s->k);
    s->k.threaded = c->threads > 0;
    reg(s, &s->extal, "extal", 1, 0);
    reg(s, &s->reset_n, "reset_n", 1, 0);
    reg(s, &s->nmi_n, "nmi_n", 1, 1);
    reg(s, &s->firq_n, "firq_n", 1, 1);
    reg(s, &s->irq_n, "irq_n", 1, 1);
    reg(s, &s->mrdy, "mrdy", 1, 1);
    reg(s, &s->dma_breq_n, "dma_breq_n", 1, 1);
    reg(s, &s->halt_n, "halt_n", 1, 1);
    reg(s, &s->e, "e", 1, 0);
    reg(s, &s->ba, "ba", 1, 0);
    reg(s, &s->bs, "bs", 1, 0);
    reg(s, &s->rw_n, "rw_n", 1, 1);
    reg(s, &s->q, "q", 1, 0);
    reg(s, &s->addr, "addr", 33, 0);
    reg(s, &s->data, "data", 64, UINT64_MAX);
    reg(s, &s->ext_eirq_n, "ext_eirq_n", 8, 0xFF);
    reg(s, &s->cpuclk, "cpuclk", 1, 0);
    reg(s, &s->sysclk, "sysclk", 1, 0);
    reg(s, &s->memclk, "memclk", 1, 0);
    reg(s, &s->fic, "fic", 1, 0);
    reg(s, &s->vma, "vma", 1, 0);
    reg(s, &s->byte_mask, "byte_mask", 8, 0);
    soc09_pia_port_data_init(&s->k, &s->pia_port_data);
    reg(s, &s->pia_c1, "pia_c1", 5, 0);
    reg(s, &s->pia_c2, "pia_c2", 5, 0);
    reg(s, &s->acia_rx, "acia_rx", 2, 3);
    reg(s, &s->acia_tx, "acia_tx", 2, 3);
    reg(s, &s->acia_rts_n, "acia_rts_n", 2, 0);
    reg(s, &s->acia_cts_n, "acia_cts_n", 2, 0);
    reg(s, &s->acia_dcd_n, "acia_dcd_n", 2, 0);
    soc09_ptm_o_init(&s->k, &s->ptm_o);
    soc09_ptm_c_n_init(&s->k, &s->ptm_c_n);
    soc09_ptm_g_n_init(&s->k, &s->ptm_g_n);
    reg(s, &s->spi_miso, "spi_miso", 1, 0);
    reg(s, &s->spi_mosi, "spi_mosi", 1, 0);
    reg(s, &s->spi_ss, "spi_ss", 16, 0xFFFF);
    reg(s, &s->spi_sclk, "spi_sclk", 1, 0);
    reg(s, &s->twi_sda, "twi_sda", 1, 1);
    reg(s, &s->twi_scl, "twi_scl", 1, 1);
    /* the open-drain pads of the peripherals : the lines are pulled up, the outside world can pull them low */
    s->twi_sda.wand = s->twi_scl.wand = 1;
    s->spi_miso.wand = s->spi_mosi.wand = s->spi_ss.wand = s->spi_sclk.wand = 1;
    s->pia_c2.wand = 1;
    for (i = 0; i < 5; i++)
    {
        s->pia_port_data.a[i].wand = 1;
        s->pia_port_data.a[i].cur = s->pia_port_data.a[i].nxt = 0xFF;      /* pulled up */
    }
    s->pia_c2.cur = s->pia_c2.nxt = 0x1F;
    s->spi_miso.cur = s->spi_miso.nxt = 1;
    s->spi_mosi.cur = s->spi_mosi.nxt = 1;
    s->spi_ss.cur = s->spi_ss.nxt = 0xFFFF;
    for (i = 0; i < 2; i++)
    {
        s->ptm_c_n.a[i].cur = s->ptm_c_n.a[i].nxt = 7;      /* external clocks idle, gates enabled (G_n = 0) */
    }
    if (soc09_create(&s->k, &s->dut, "soc", 5, 2, 2, !c->fpu_shared, c->ncpus, &s->extal, &s->reset_n, &s->nmi_n,
                     &s->firq_n, &s->irq_n, &s->mrdy, &s->dma_breq_n, &s->halt_n, &s->e, &s->ba, &s->bs, &s->rw_n,
                     &s->q, &s->addr, &s->data, &s->ext_eirq_n, &s->cpuclk, &s->sysclk, &s->memclk, &s->fic,
                     &s->vma, &s->byte_mask, &s->pia_port_data, &s->pia_c1, &s->pia_c2, &s->acia_rx, &s->acia_tx,
                     &s->acia_rts_n, &s->acia_cts_n, &s->acia_dcd_n, &s->ptm_o, &s->ptm_c_n, &s->ptm_g_n,
                     &s->spi_miso, &s->spi_mosi, &s->spi_ss, &s->spi_sclk, &s->twi_sda, &s->twi_scl) != 0)
    {
        return -1;
    }
    if (c->twi_eeprom)
    {
        i2c_eeprom_create(&s->k, &s->eeprom, &s->twi_sda, &s->twi_scl, c->twi_eeprom_addr);
        i2c_eeprom_options(&s->eeprom, c->twi_eeprom_page, (uint64_t) c->twi_eeprom_write_us * 144000, c->twi_eeprom_file);
    }
    if (c->spi_slave)
    {
        spi_slave_create(&s->k, &s->spi, &s->spi_ss, &s->spi_sclk, &s->spi_mosi, &s->spi_miso);
    }
    if (c->pins_socket[0] != '\0' && pins_setup(s) != 0)
    {
        return -1;
    }
    find_trace_signals(s);
    sens[0] = &s->addr;
    sens[1] = &s->e;
    sens[2] = &s->rw_n;
    sens[3] = &s->vma;
    vs_register_process(&s->k, companion_run, s, sens, 4);
    sens[0] = &s->acia_tx;
    vs_register_process(&s->k, tx_run, s, sens, 1);
    sens[0] = &s->twi_sda;
    sens[1] = &s->twi_scl;
    vs_register_process(&s->k, i2c_log, s, sens, 2);
    /* the serial lines : ACIA_RX(i) and ACIA_TX(i) are bits (1 - i) of the vectors (0 to 1) */
    for (i = 0; i < SOC_NACIA; i++)
    {
        if (!c->serial[i].enabled)
        {
            continue;
        }
        vs_register_signal(&s->k, &s->con_rx[i], 1);
        vs_register_signal(&s->k, &s->con_tx[i], 1);
        vs_tie_fields(&s->con_rx[i], 0, &s->acia_rx, (unsigned) (SOC_NACIA - 1 - i), 1);
        vs_tie_fields(&s->acia_tx, (unsigned) (SOC_NACIA - 1 - i), &s->con_tx[i], 0, 1);
        console_init(&s->con[i]);
        if (c->serial[i].socket[0] != '\0' && console_listen(&s->con[i], c->serial[i].socket, c->serial[i].wait) != 0)
        {
            return -1;
        }
        console_create(&s->k, &s->con[i], &s->con_rx[i], &s->con_tx[i], c->serial[i].baud,
                       c->serial[i].socket[0] ? NULL : c->serial[i].in, c->serial[i].socket[0] ? NULL : c->serial[i].out);
    }
    vs_clock_source(&s->k, &s->extal, SOC_EXTAL_HALF, SOC_EXTAL_HALF);
    vs_timer_add(&s->k, c->reset_ticks, release_reset, s);
    return 0;
}

static volatile sig_atomic_t stop_requested;

static void on_signal(int sig)
{
    (void) sig;
    stop_requested = 1;
}

void soc_run(soc *s)
{
    int saved = 0;
    struct sigaction sa;

    /* SIGINT (Ctrl-C) and SIGTERM end the run cleanly: the sockets are closed, the snapshot is written (--save). A second
     * signal kills the process as usual (SA_RESETHAND). */
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_signal;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESETHAND;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    vs_settle(&s->k);
    if (s->cfg.threads > 1 && s->k.nparts > 1 && vs_threads_start(&s->k, (unsigned) s->cfg.threads) != 0)
    {
        fprintf(stderr, "cannot start the threads\n");
        return;
    }
    if (s->cfg.dump != NULL)
    {
        vs_dump(&s->k, s->cfg.dump, 0);
    }
    while (!vs_finished && !stop_requested && (s->cfg.max_ticks == 0 || s->k.now < s->cfg.max_ticks) && vs_advance(&s->k))
    {
        if (s->cfg.dump != NULL)
        {
            vs_dump(&s->k, s->cfg.dump, (long) s->k.now);
        }
        if (!saved && s->cfg.save_path[0] != '\0' && s->cfg.save_at != 0 && s->k.now >= s->cfg.save_at)
        {
            saved = 1;
            if (snapshot_save(s, s->cfg.save_path) == 0)
            {
                fprintf(stderr, "snapshot written at %llu ticks : %s\n", (unsigned long long) s->k.now, s->cfg.save_path);
            }
        }
    }
    vs_threads_stop(&s->k);
    if (s->cfg.twi_eeprom)
    {
        i2c_eeprom_save(&s->eeprom);
    }
    if (stop_requested)
    {
        fprintf(stderr, "interrupted at %llu ticks\n", (unsigned long long) s->k.now);
    }
    if (!saved && s->cfg.save_path[0] != '\0' && snapshot_save(s, s->cfg.save_path) == 0)
    {
        fprintf(stderr, "snapshot written at %llu ticks : %s\n", (unsigned long long) s->k.now, s->cfg.save_path);
    }
}

void soc_destroy(soc *s)
{
    int i;

    if (s->cfg.pins_socket[0] != '\0')
    {
        pins_close(&s->pins);
    }
    for (i = 0; i < SOC_NACIA; i++)
    {
        if (s->cfg.serial[i].enabled)
        {
            console_close(&s->con[i]);
        }
    }
    vs_kernel_free(&s->k);
}
