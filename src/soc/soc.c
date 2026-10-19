#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"

void soc_cfg_default(soc_cfg *c)
{
    memset(c, 0, sizeof(*c));
    c->ncpus = 1;
    c->fpu_shared = 0;
    /* A is 36 bits wide. Without MMU the physical address is 0xF followed by the 32 bits of the core, so a program
     * linked at 0x00000000 runs at 0xF00000000, and the reset vector sits at 0xFFFFFFFFE. */
    c->elf_offset = UINT64_C(0xF00000000);
    c->bac_base = UINT64_C(0xFFFFE0000);
    c->mmu_base = UINT64_C(0xFFFFE1000);
    c->reset_ticks = 10 * 2 * SOC_EXTAL_HALF;       /* ten EXTAL periods */
}

int soc_add_zone(soc_cfg *c, uint64_t base, uint64_t size, int writable)
{
    soc_zone    *z;

    if (c->nzones == SOC_MAX_ZONES || size == 0)
    {
        return -1;
    }
    z = &c->zones[c->nzones];
    z->data = malloc((size_t) size);
    if (z->data == NULL)
    {
        return -1;
    }
    memset(z->data, writable ? 0 : 0xFF, (size_t) size);
    z->base = base;
    z->size = size;
    z->writable = writable;
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

/* The external bus : decoding of the chip selects, read data and write capture. */
static void bus_run(void *inst)
{
    soc         *s = inst;
    uint64_t    a = s->a.cur;
    int         in_bac = a >= s->cfg.bac_base && a < s->cfg.bac_base + 32;
    int         in_mmu = a >= s->cfg.mmu_base && a < s->cfg.mmu_base + 4096;
    soc_zone    *z = find_zone(&s->cfg, a);
    uint64_t    owner = s->bus_master.cur;

    vs_drive(&s->cs, in_bac);
    vs_drive(&s->mmu_cs, in_mmu ? UINT64_C(1) << owner : 0);
    vs_drive(&s->cacheable, !(in_bac || in_mmu));
    vs_drive(&s->mrdy, s->mux_mrdy.cur & s->mmu_mrdy.cur);
    if (in_bac)
    {
        vs_drive(&s->d_in, s->mux_d_out.cur);
    }
    else if (z != NULL)
    {
        vs_drive(&s->d_in, z->data[a - z->base]);
    }
    else
    {
        vs_drive(&s->d_in, 0xFF);
    }
    if (s->cfg.trace_bus && vs_falling(&s->e))
    {
        printf("%12llu bus %llu A=%09llX %c VMA=%d BA=%d BS=%d D=%02X\n", (unsigned long long) s->k.now,
               (unsigned long long) owner, (unsigned long long) a, s->rw_n.cur ? 'R' : 'W', (int) s->vma.cur,
               (int) s->ba.cur, (int) s->bs.cur, (unsigned) (s->rw_n.cur ? s->d_in.cur : s->d_out.cur));
    }
    if (vs_falling(&s->e) && s->vma.cur == 1 && s->ba.cur == 0)
    {
        if (s->rw_n.cur == 0)
        {
            s->writes++;
            if (z != NULL && z->writable)
            {
                z->data[a - z->base] = (uint8_t) s->d_out.cur;
            }
            else if (z == NULL && !in_bac && !in_mmu)
            {
                s->unmapped++;
            }
        }
        else
        {
            s->reads++;
            if (z == NULL && !in_bac && !in_mmu)
            {
                s->unmapped++;
            }
        }
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

int soc_create(soc *s, const soc_cfg *c)
{
    vs_sig  *sens[7];

    if (c->ncpus < 1 || c->ncpus > 8)
    {
        fprintf(stderr, "the number of CPUs goes from 1 to 8\n");
        return -1;
    }
    s->cfg = *c;
    s->reads = s->writes = s->unmapped = 0;
    vs_kernel_init(&s->k);
    reg(s, &s->extal, "extal", 1, 0);
    reg(s, &s->reset_n, "reset_n", 1, 0);
    reg(s, &s->nmi_n, "nmi_n", 1, 1);
    reg(s, &s->firq_n, "firq_n", 1, 1);
    reg(s, &s->irq_n, "irq_n", 1, 1);
    reg(s, &s->mrdy, "mrdy", 1, 1);
    reg(s, &s->dma_breq_n, "dma_breq_n", 1, 1);
    reg(s, &s->halt_n, "halt_n", 1, 1);
    reg(s, &s->e, "e", 1, 0);
    reg(s, &s->e_n, "e_n", 1, 1);
    reg(s, &s->q, "q", 1, 0);
    reg(s, &s->ba, "ba", 1, 0);
    reg(s, &s->bs, "bs", 1, 0);
    reg(s, &s->rw_n, "rw_n", 1, 1);
    reg(s, &s->vma, "vma", 1, 0);
    reg(s, &s->a, "a", 36, 0);
    reg(s, &s->d_in, "d_in", 8, 0xFF);
    reg(s, &s->d_out, "d_out", 8, 0);
    reg(s, &s->eirq_n, "eirq_n", 24, 0xFFFFFF);
    reg(s, &s->fic, "fic", 1, 0);
    reg(s, &s->cacheable, "cacheable", 1, 1);
    reg(s, &s->sysclk, "sysclk", 1, 0);
    reg(s, &s->cpuclk, "cpuclk", 1, 0);
    reg(s, &s->memclk, "memclk", 1, 0);
    reg(s, &s->cs, "cs", 1, 0);
    reg(s, &s->mmu_cs, "mmu_cs", 8, 0);
    reg(s, &s->mmu_mrdy, "mmu_mrdy", 1, 1);
    reg(s, &s->mux_d_in, "mux_d_in", 8, 0);
    reg(s, &s->mux_d_out, "mux_d_out", 8, 0);
    reg(s, &s->mux_mrdy, "mux_mrdy", 1, 1);
    reg(s, &s->bus_master, "bus_master", 64, 0);
    bac_63f81_create(&s->k, &s->bac, "soc.bac", c->ncpus, !c->fpu_shared, &s->extal, &s->reset_n, &s->nmi_n,
                     &s->firq_n, &s->irq_n, &s->mrdy, &s->dma_breq_n, &s->halt_n, &s->e, &s->e_n, &s->q, &s->ba,
                     &s->bs, &s->rw_n, &s->vma, &s->a, &s->d_in, &s->d_out, &s->eirq_n, &s->fic, &s->cacheable,
                     &s->sysclk, &s->cpuclk, &s->memclk, &s->cs, &s->mmu_cs, &s->mmu_mrdy, &s->mux_d_in,
                     &s->mux_d_out, &s->mux_mrdy, &s->bus_master);
    sens[0] = &s->a;
    sens[1] = &s->e;
    sens[2] = &s->mux_d_out;
    sens[3] = &s->mux_mrdy;
    sens[4] = &s->mmu_mrdy;
    sens[5] = &s->bus_master;
    sens[6] = &s->vma;
    vs_register_process(&s->k, bus_run, s, sens, 7);
    vs_clock_source(&s->k, &s->extal, SOC_EXTAL_HALF, SOC_EXTAL_HALF);
    vs_timer_add(&s->k, c->reset_ticks, release_reset, s);
    return 0;
}

void soc_run(soc *s)
{
    vs_settle(&s->k);
    while (!vs_finished && (s->cfg.max_ticks == 0 || s->k.now < s->cfg.max_ticks) && vs_advance(&s->k))
    {
    }
}

void soc_destroy(soc *s)
{
    int i;

    for (i = 0; i < s->cfg.nzones; i++)
    {
        free(s->cfg.zones[i].data);
    }
    vs_kernel_free(&s->k);
}
