#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/mman.h>

#include "vsim.h"

vs_part  *vs_parts[VS_MAX_PARTS];
uint32_t vs_gen = 1;
int     vs_finished;
static int mapped_ok;

/* One arena at a fixed address holds everything that a run allocates : the kernel, the instances, the models, the memories.
 * A snapshot is the content of the arena (plus the three globals above) : the pointers inside stay valid when it is
 * loaded again at the same address, in the same executable (linked without PIE). Blocks are never freed ; the first
 * 16 bytes of the arena are the header, each block has a 16-byte header with its size. */
#define ARENA_BASE  ((uint8_t *) UINT64_C(0x200000000000))
#define ARENA_CAP   (UINT64_C(4) << 30)

typedef struct arena_hdr
{
    size_t      used;
    size_t      pad;
} arena_hdr;

int vs_arena_map(void)
{
    void    *p;

    if (mapped_ok)
    {
        return 0;
    }
#ifdef MAP_FIXED_NOREPLACE
    p = mmap(ARENA_BASE, ARENA_CAP, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED_NOREPLACE, -1, 0);
#else
    p = mmap(ARENA_BASE, ARENA_CAP, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
#endif
    if (p != (void *) ARENA_BASE)
    {
        fprintf(stderr, "cannot map the arena at %p\n", (void *) ARENA_BASE);
        return -1;
    }
    ((arena_hdr *) ARENA_BASE)->used = sizeof(arena_hdr);
    mapped_ok = 1;
    return 0;
}

void vs_arena_region(void **base, size_t *used)
{
    *base = ARENA_BASE;
    *used = ((arena_hdr *) ARENA_BASE)->used;
}

void vs_arena_set_used(size_t used)
{
    ((arena_hdr *) ARENA_BASE)->used = used;
}

void *vs_arena_alloc(size_t n)
{
    arena_hdr   *h;
    uint8_t     *p;

    if (vs_arena_map() != 0)
    {
        abort();
    }
    h = (arena_hdr *) ARENA_BASE;
    n = (n + 15) & ~(size_t) 15;
    if (h->used + 16 + n > ARENA_CAP)
    {
        fprintf(stderr, "arena full\n");
        abort();
    }
    p = ARENA_BASE + h->used;
    *(size_t *) p = n;                  /* fresh pages of the mapping are zero */
    h->used += 16 + n;
    return p + 16;
}

static void *xrealloc(void *old, size_t n)
{
    uint8_t *p = old;
    size_t  on;
    void    *q;

    if (p == NULL)
    {
        return vs_arena_alloc(n ? n : 1);
    }
    on = *(size_t *) (p - 16);
    if (n <= on)
    {
        return p;
    }
    if (p + on == ARENA_BASE + ((arena_hdr *) ARENA_BASE)->used)       /* the last block grows in place */
    {
        size_t  nn = (n + 15) & ~(size_t) 15;

        if (((arena_hdr *) ARENA_BASE)->used + (nn - on) <= ARENA_CAP)
        {
            *(size_t *) (p - 16) = nn;
            ((arena_hdr *) ARENA_BASE)->used += nn - on;
            return p;
        }
    }
    q = vs_arena_alloc(n < 2 * on ? 2 * on : n);        /* geometric growth : the old block is not reused */
    memcpy(q, p, on);
    return q;
}

void vs_part_enter(vs_kernel *k, unsigned part)
{
    if (part >= VS_MAX_PARTS)
    {
        abort();
    }
    while (k->nparts <= part)
    {
        vs_parts[k->nparts] = xrealloc(NULL, sizeof(vs_part));
        memset(vs_parts[k->nparts], 0, sizeof(vs_part));
        k->nparts++;
    }
    k->cur_part = part;
}

void vs_parts_reset(vs_kernel *k)
{
    unsigned    i, j;

    for (i = 0; i < k->nparts; i++)
    {
        for (j = 0; j < VS_MAX_PARTS; j++)
        {
            vs_parts[i]->mail[j] = NULL;            /* scratch lists : malloc'ed, not part of a snapshot */
            vs_parts[i]->nmail[j] = vs_parts[i]->cmail[j] = 0;
        }
    }
}

void vs_kernel_init(vs_kernel *k)
{
    memset(k, 0, sizeof(*k));
    vs_finished = 0;
    vs_gen = 1;
    vs_part_enter(k, 0);
}

void vs_name(vs_kernel *k, vs_sig *s, const char *path, const char *name, unsigned width)
{
    size_t  lp = path ? strlen(path) : 0;
    size_t  n = lp + (lp ? 1 : 0) + strlen(name) + 1;
    char    *p = xrealloc(NULL, n);

    snprintf(p, n, "%s%s%s", path ? path : "", lp ? "." : "", name);
    if (k->nnames == k->cnames)
    {
        k->cnames = k->cnames ? k->cnames * 2 : 256;
        k->names = xrealloc(k->names, k->cnames * sizeof(*k->names));
    }
    k->names[k->nnames++] = p;
    s->name = p;
    s->width = width;
}

const char *vs_join(vs_kernel *k, const char *a, const char *b)
{
    size_t  la = a ? strlen(a) : 0;
    size_t  n = la + (la ? 1 : 0) + strlen(b) + 1;
    char    *p = xrealloc(NULL, n);

    snprintf(p, n, "%s%s%s", a ? a : "", la ? "." : "", b);
    if (k->nnames == k->cnames)
    {
        k->cnames = k->cnames ? k->cnames * 2 : 256;
        k->names = xrealloc(k->names, k->cnames * sizeof(*k->names));
    }
    k->names[k->nnames++] = p;
    return p;
}

void vs_dump(vs_kernel *k, FILE *f, long phase)
{
    size_t  i;

    for (i = 0; i < k->nsigs; i++)
    {
        vs_sig  *s = k->sigs[i];

        if (s->name != NULL && (!s->dumped || s->last != s->cur))
        {
            fprintf(f, "%ld %s %llu\n", phase, s->name, (unsigned long long) s->cur);
            s->last = s->cur;
            s->dumped = 1;
        }
    }
}

void *vs_alloc(vs_kernel *k, size_t size)
{
    void    *p = xrealloc(NULL, size);

    memset(p, 0, size);
    if (k->nallocs == k->callocs)
    {
        k->callocs = k->callocs ? k->callocs * 2 : 64;
        k->allocs = xrealloc(k->allocs, k->callocs * sizeof(*k->allocs));
    }
    k->allocs[k->nallocs++] = p;
    return p;
}

void vs_tie_fields(vs_sig *src, unsigned src_shift, vs_sig *dst, unsigned dst_shift, unsigned width)
{
    uint64_t    mask = width >= 64 ? UINT64_MAX : (UINT64_C(1) << width) - 1;
    uint64_t    v = (src->cur >> src_shift) & mask;

    src->ties = xrealloc(src->ties, (src->nties + 1) * sizeof(*src->ties));
    if (src->wand || dst->wand)
    {
        src->wand = dst->wand = 1;        /* the nets that are tied are one pad */
    }
    src->ties[src->nties].dst = dst;
    src->ties[src->nties].dst_shift = dst_shift;
    src->ties[src->nties].src_shift = src_shift;
    src->ties[src->nties].mask = mask;
    src->nties++;
    dst->cur = (dst->cur & ~(mask << dst_shift)) | (v << dst_shift);
    dst->nxt = (dst->nxt & ~(mask << dst_shift)) | (v << dst_shift);
}

void vs_timer_add(vs_kernel *k, uint64_t when, void (*fn)(vs_kernel *, void *), void *arg)
{
    size_t  i;

    if (k->ntimers == k->ctimers)
    {
        k->ctimers = k->ctimers ? k->ctimers * 2 : 16;
        k->timers = xrealloc(k->timers, k->ctimers * sizeof(*k->timers));
    }
    /* after the timers of the same time : they run in the order they were added */
    i = k->ntimers;
    while (i > 0 && k->timers[i - 1].when > when)
    {
        k->timers[i] = k->timers[i - 1];
        i--;
    }
    k->timers[i].when = when;
    k->timers[i].fn = fn;
    k->timers[i].arg = arg;
    k->ntimers++;
}

int vs_advance(vs_kernel *k)
{
    uint64_t    t;

    if (k->ntimers == 0)
    {
        return 0;
    }
    t = k->timers[0].when;
    k->now = t;
    while (k->ntimers > 0 && k->timers[0].when == t)
    {
        vs_timer    due = k->timers[0];

        memmove(k->timers, k->timers + 1, (k->ntimers - 1) * sizeof(*k->timers));
        k->ntimers--;
        due.fn(k, due.arg);
    }
    vs_settle(k);
    return 1;
}

typedef struct clock_source
{
    vs_sig      *s;
    uint64_t    half;
} clock_source;

static void clock_tick(vs_kernel *k, void *arg)
{
    clock_source    *c = arg;

    vs_drive(c->s, c->s->cur ^ 1);
    vs_timer_add(k, k->now + c->half, clock_tick, c);
}

void vs_clock_source(vs_kernel *k, vs_sig *s, uint64_t first, uint64_t half)
{
    clock_source    *c = vs_alloc(k, sizeof(*c));

    c->s = s;
    c->half = half;
    vs_timer_add(k, first, clock_tick, c);
}

void vs_pull(vs_sig *s, uint64_t mask, int low)
{
    uint64_t    pulled = low ? (s->pulled | mask) : (s->pulled & ~mask);
    uint32_t    m;

    if (pulled == s->pulled)
    {
        return;
    }
    s->pulled = pulled;
    vs_drive(s, s->nxt);                /* the effective value is recomputed at the next commit */
    for (m = 0; m < s->nties; m++)      /* the nets tied to the pad are the same wire : they are pulled too */
    {
        vs_tie      *t = &s->ties[m];
        uint64_t    bits = (mask >> t->src_shift) & t->mask;

        if (bits != 0)
        {
            vs_pull(t->dst, bits << t->dst_shift, low);
        }
    }
}

void vs_region_add(vs_kernel *k, const char *path, uint8_t *data, size_t size)
{
    if (k->nregions == k->cregions)
    {
        k->cregions = k->cregions ? k->cregions * 2 : 8;
        k->regions = xrealloc(k->regions, k->cregions * sizeof(*k->regions));
    }
    k->regions[k->nregions].path = path;
    k->regions[k->nregions].data = data;
    k->regions[k->nregions].size = size;
    k->nregions++;
}

vs_region *vs_region_find(vs_kernel *k, const char *suffix)
{
    size_t  i, ls = strlen(suffix);

    for (i = 0; i < k->nregions; i++)
    {
        size_t  lp = strlen(k->regions[i].path);

        if (lp >= ls && strcasecmp(k->regions[i].path + lp - ls, suffix) == 0)
        {
            return &k->regions[i];
        }
    }
    return NULL;
}

void vs_kernel_free(vs_kernel *k)
{
    unsigned    i, j;

    /* the memory is in the arena : nothing to free, the process is ending (only the scratch lists are malloc'ed) */
    for (i = 0; i < k->nparts; i++)
    {
        for (j = 0; j < VS_MAX_PARTS; j++)
        {
            free(vs_parts[i]->mail[j]);
        }
        vs_parts[i] = NULL;
    }
    memset(k, 0, sizeof(*k));
}

void vs_register_signal(vs_kernel *k, vs_sig *s, uint64_t init)
{
    s->cur = init;
    s->nxt = init;
    s->pend = 0;
    s->evt = 0;
    s->part = (uint8_t) k->cur_part;
    s->fan = NULL;
    s->nfan = 0;
    s->name = NULL;
    s->width = 0;
    s->last = 0;
    s->dumped = 0;
    s->ties = NULL;
    s->nties = 0;
    s->pulled = 0;
    s->wand = 0;
    if (k->nsigs == k->csigs)
    {
        k->csigs = k->csigs ? k->csigs * 2 : 256;
        k->sigs = xrealloc(k->sigs, k->csigs * sizeof(*k->sigs));
    }
    k->sigs[k->nsigs++] = s;
}

void vs_register_process_edges(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, const uint64_t *masks,
                               const uint8_t *edges, size_t nsens)
{
    vs_proc *p = xrealloc(NULL, sizeof(*p));

    p->run = run;
    p->inst = inst;
    p->nsens = nsens;
    p->queued = 0;
    p->part = (uint8_t) k->cur_part;
    p->sens = xrealloc(NULL, nsens * sizeof(*p->sens));
    memcpy(p->sens, sens, nsens * sizeof(*p->sens));
    p->masks = NULL;
    p->edges = NULL;
    if (edges != NULL)
    {
        p->edges = xrealloc(NULL, nsens * sizeof(*p->edges));
        memcpy(p->edges, edges, nsens * sizeof(*p->edges));
    }
    if (masks != NULL)
    {
        p->masks = xrealloc(NULL, nsens * sizeof(*p->masks));
        memcpy(p->masks, masks, nsens * sizeof(*p->masks));
    }
    if (k->nprocs == k->cprocs)
    {
        k->cprocs = k->cprocs ? k->cprocs * 2 : 256;
        k->procs = xrealloc(k->procs, k->cprocs * sizeof(*k->procs));
    }
    k->procs[k->nprocs++] = p;
}

void vs_register_process_masked(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, const uint64_t *masks,
                                size_t nsens)
{
    vs_register_process_edges(k, run, inst, sens, masks, NULL, nsens);
}

void vs_register_process(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, size_t nsens)
{
    vs_register_process_masked(k, run, inst, sens, NULL, nsens);
}

/* Builds the per-signal lists of the processes to wake, and the work areas. */
static void finalise(vs_kernel *k)
{
    size_t  i, j;

    for (i = 0; i < k->nprocs; i++)
    {
        vs_proc *p = k->procs[i];

        for (j = 0; j < p->nsens; j++)
        {
            vs_sig      *s = p->sens[j];
            uint64_t    mask = p->masks != NULL ? p->masks[j] : UINT64_MAX;
            uint8_t     edge = p->edges != NULL ? p->edges[j] : 0;
            size_t      m;
            int         dup = 0;

            for (m = 0; m < s->nfan; m++)
            {
                if (s->fan[m].p == p)
                {
                    s->fan[m].mask |= mask;     /* the same process, several bits */
                    if (s->fan[m].edge != edge)
                    {
                        s->fan[m].edge = 0;
                    }
                    dup = 1;
                    break;
                }
            }
            if (!dup)
            {
                s->fan = xrealloc(s->fan, (s->nfan + 1) * sizeof(*s->fan));
                s->fan[s->nfan].p = p;
                s->fan[s->nfan].mask = mask;
                s->fan[s->nfan].edge = edge;
                s->nfan++;
            }
        }
    }
    for (i = 0; i < k->nparts; i++)
    {
        size_t  ns = 0, np = 0;

        for (j = 0; j < k->nsigs; j++)
        {
            ns += k->sigs[j]->part == i;
        }
        for (j = 0; j < k->nprocs; j++)
        {
            np += k->procs[j]->part == i;
        }
        vs_parts[i]->runq = xrealloc(NULL, (np ? np : 1) * sizeof(*vs_parts[i]->runq));
        vs_parts[i]->pend = xrealloc(NULL, (ns ? ns : 1) * sizeof(*vs_parts[i]->pend));
        vs_parts[i]->nrun = vs_parts[i]->npend = 0;
    }
    k->finalised = 1;
}

/* A signal has changed in the commit `next` of partition `cp`: it raises its event, wakes the processes (those of other
 * partitions through the mail), and the nets tied to it follow. */
static void changed(vs_kernel *k, unsigned cp, vs_sig *s, uint32_t next)
{
    uint32_t    m;
    vs_part     *pt = vs_parts[cp];

    s->evt = next;
    for (m = 0; m < s->nfan; m++)
    {
        vs_proc *p = s->fan[m].p;

        if (s->fan[m].mask != UINT64_MAX && ((s->prev ^ s->cur) & s->fan[m].mask) == 0)
        {
            continue;           /* a bit of the signal changed, but not the one in the sensitivity list */
        }
        if (s->fan[m].edge != 0 && ((s->cur & 1) == 1) != (s->fan[m].edge == 1))
        {
            continue;           /* the process only looks at the other edge */
        }
        if (p->part == cp)
        {
            if (!p->queued)
            {
                p->queued = 1;
                pt->runq[pt->nrun++] = p;
            }
        }
        else
        {
            unsigned    t = p->part;

            if (pt->nmail[t] == pt->cmail[t])
            {
                pt->cmail[t] = pt->cmail[t] ? pt->cmail[t] * 2 : 256;
                pt->mail[t] = realloc(pt->mail[t], pt->cmail[t] * sizeof(*pt->mail[t]));
                if (pt->mail[t] == NULL)
                {
                    abort();
                }
            }
            pt->mail[t][pt->nmail[t]++] = p;
        }
    }
    for (m = 0; m < s->nties; m++)
    {
        vs_tie      *t = &s->ties[m];
        uint64_t    v = (s->cur >> t->src_shift) & t->mask;
        uint64_t    n = (t->dst->cur & ~(t->mask << t->dst_shift)) | (v << t->dst_shift);

        if (n != t->dst->cur)
        {
            if (t->dst->evt != next)
            {
                t->dst->prev = t->dst->cur;
            }
            t->dst->cur = n;
            t->dst->nxt = (t->dst->nxt & ~(t->mask << t->dst_shift)) | (v << t->dst_shift);
            changed(k, cp, t->dst, next);
        }
    }
}

/* Commit the pending values of partition `cp`. */
static void commit(vs_kernel *k, unsigned cp)
{
    vs_part     *pt = vs_parts[cp];
    uint32_t    next = vs_gen + 1;
    size_t      i;

    for (i = 0; i < pt->npend; i++)
    {
        vs_sig  *s = pt->pend[i];

        uint64_t    eff = s->nxt & ~s->pulled;

        s->pend = 0;
        if (eff != s->cur)
        {
            if (s->evt != next)
            {
                s->prev = s->cur;
            }
            s->cur = eff;
            changed(k, cp, s, next);
        }
    }
    pt->npend = 0;
}

/* The processes that the other partitions woke join the run queue. */
static void merge_mail(vs_kernel *k, unsigned me)
{
    vs_part *pt = vs_parts[me];
    unsigned    src;
    size_t      i;

    for (src = 0; src < k->nparts; src++)
    {
        vs_part *from = vs_parts[src];

        if (src == me)
        {
            continue;
        }
        for (i = 0; i < from->nmail[me]; i++)
        {
            vs_proc *p = from->mail[me][i];

            if (!p->queued)
            {
                p->queued = 1;
                pt->runq[pt->nrun++] = p;
            }
        }
        from->nmail[me] = 0;
    }
}

/* The end of a commit round, for all the partitions : the new events are the ones of the next generation. */
static void next_generation(vs_kernel *k)
{
    unsigned    i;

    if (++vs_gen == 0)                  /* wrapped : the stamps of the old events must not match again */
    {
        size_t  j;

        for (j = 0; j < k->nsigs; j++)
        {
            k->sigs[j]->evt = 0;
        }
        vs_gen = 1;
    }
    for (i = 0; i < k->nparts; i++)
    {
        merge_mail(k, i);
    }
}

static int work_left(vs_kernel *k)
{
    unsigned    i;

    for (i = 0; i < k->nparts; i++)
    {
        if (vs_parts[i]->nrun > 0)
        {
            return 1;
        }
    }
    return 0;
}

uint64_t vs_settle(vs_kernel *k)
{
    uint64_t    start = k->deltas;
    size_t      i;
    unsigned    pi;

    if (!k->finalised)
    {
        finalise(k);
    }

    if (!k->initialised)
    {
        /* Initialisation phase : every process runs once, before anything else is seen. */
        k->initialised = 1;
        for (i = 0; i < k->nprocs; i++)
        {
            k->procs[i]->run(k->procs[i]->inst);
        }
        k->deltas++;
    }

    /* Values driven by the test bench, or by the initialisation phase. */
    for (pi = 0; pi < k->nparts; pi++)
    {
        commit(k, pi);
    }
    next_generation(k);

    while (work_left(k))
    {
        /* Processes see the events of the previous commit while they run. Nothing is queued while they run (queueing is
         * done by commit), so the flag of a process can be cleared just before it runs. */
        for (pi = 0; pi < k->nparts; pi++)
        {
            vs_part *pt = vs_parts[pi];
            size_t  n = pt->nrun;

            pt->nrun = 0;
            for (i = 0; i < n; i++)
            {
                vs_proc *p = pt->runq[i];

                p->queued = 0;
                p->run(p->inst);
            }
        }
        k->deltas++;
        for (pi = 0; pi < k->nparts; pi++)
        {
            commit(k, pi);
        }
        next_generation(k);
    }
    return k->deltas - start;
}
