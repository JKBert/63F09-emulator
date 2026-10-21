#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <pthread.h>
#include <sched.h>
#include <sys/mman.h>
#include <unistd.h>

#include "vsim.h"

vs_part  *vs_parts[VS_MAX_PARTS];
uint32_t vs_gen = 1;
unsigned long long vs_stat_max, vs_stat_tot;
unsigned long long vs_stat_runs[VS_MAX_PARTS];     /* processes run, per partition (sequential mode) */
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
    unsigned    i, j, q;

    for (i = 0; i < k->nparts; i++)
    {
        for (q = 0; q < 2; q++)
        {
            for (j = 0; j < VS_MAX_PARTS; j++)
            {
                vs_parts[i]->mail[q][j] = NULL;     /* scratch lists : malloc'ed, not part of a snapshot */
                vs_parts[i]->nmail[q][j] = vs_parts[i]->cmail[q][j] = 0;
                vs_parts[i]->xq[q][j] = NULL;
                vs_parts[i]->nxq[q][j] = vs_parts[i]->cxq[q][j] = 0;
            }
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

void vs_tie_all(vs_sig **src, vs_sig **dst, size_t n)
{
    size_t  i;

    for (i = 0; i < n; i++)
    {
        vs_tie_fields(src[i], 0, dst[i], 0, 64);
    }
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
    unsigned    i, j, q;

    /* the memory is in the arena : nothing to free, the process is ending (only the scratch lists are malloc'ed) */
    for (i = 0; i < k->nparts; i++)
    {
        for (q = 0; q < 2; q++)
        {
            for (j = 0; j < VS_MAX_PARTS; j++)
            {
                free(vs_parts[i]->mail[q][j]);
                free(vs_parts[i]->xq[q][j]);
            }
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

/* A tie chain : the destination of the tie is the source of one that leaves its partition. */
static int reaches_cross(vs_sig *s, int depth)
{
    uint32_t    m;

    if (depth > 8)
    {
        return 1;
    }
    for (m = 0; m < s->nties; m++)
    {
        if (s->ties[m].dst->part != s->part || reaches_cross(s->ties[m].dst, depth + 1))
        {
            return 1;
        }
    }
    return 0;
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
    for (j = 0; j < k->nsigs; j++)
    {
        vs_sig  *sg = k->sigs[j];
        uint32_t m;

        for (m = 0; m < sg->nties; m++)
        {
            sg->ties[m].chain = reaches_cross(sg->ties[m].dst, 0);
        }
    }
    k->finalised = 1;
}

static void changed(vs_kernel *k, unsigned cp, vs_sig *s, uint32_t stamp, unsigned qp);

/* The destination of a tie takes the new value of the field of its source. */
static void follow_tie(vs_kernel *k, unsigned cp, vs_tie *t, uint64_t v, uint32_t stamp, unsigned qp)
{
    uint64_t    n = (t->dst->cur & ~(t->mask << t->dst_shift)) | (v << t->dst_shift);

    if (n != t->dst->cur)
    {
        if (t->dst->evt != stamp)
        {
            t->dst->prev = t->dst->cur;
        }
        t->dst->cur = n;
        t->dst->nxt = (t->dst->nxt & ~(t->mask << t->dst_shift)) | (v << t->dst_shift);
        changed(k, cp, t->dst, stamp, qp);
    }
}

/* A signal has changed in the commit `next` of partition `cp`: it raises its event, wakes the processes (those of other
 * partitions through the mail), and the nets tied to it follow. */
static void changed(vs_kernel *k, unsigned cp, vs_sig *s, uint32_t stamp, unsigned qp)
{
    uint32_t    m;
    vs_part     *pt = vs_parts[cp];

    s->evt = stamp;
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
            unsigned    t = p->part, q = qp;

            if (pt->nmail[q][t] == pt->cmail[q][t])
            {
                pt->cmail[q][t] = pt->cmail[q][t] ? pt->cmail[q][t] * 2 : 256;
                pt->mail[q][t] = realloc(pt->mail[q][t], pt->cmail[q][t] * sizeof(*pt->mail[q][t]));
                if (pt->mail[q][t] == NULL)
                {
                    abort();
                }
            }
            pt->mail[q][t][pt->nmail[q][t]++] = p;
        }
    }
    for (m = 0; m < s->nties; m++)
    {
        vs_tie      *t = &s->ties[m];
        uint64_t    v = (s->cur >> t->src_shift) & t->mask;

        if (t->dst->part != cp)
        {
            unsigned    d = t->dst->part, q = qp;

            if (pt->nxq[q][d] == pt->cxq[q][d])
            {
                pt->cxq[q][d] = pt->cxq[q][d] ? pt->cxq[q][d] * 2 : 256;
                pt->xq[q][d] = realloc(pt->xq[q][d], pt->cxq[q][d] * sizeof(*pt->xq[q][d]));
                if (pt->xq[q][d] == NULL)
                {
                    abort();
                }
            }
            pt->xq[q][d][pt->nxq[q][d]].t = t;
            pt->xq[q][d][pt->nxq[q][d]].v = v;
            pt->nxq[q][d]++;
        }
        else
        {
            follow_tie(k, cp, t, v, stamp, qp);
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
            changed(k, cp, s, next, next & 1);
        }
    }
    pt->npend = 0;
}

/* Partition `me` takes what the others left for it in the commit that has just ended (the generation vs_gen): the processes
 * they woke join its run queue, the ties that reach its signals are followed. */
static void apply_incoming(vs_kernel *k, unsigned me, unsigned q)
{
    vs_part     *pt = vs_parts[me];
    unsigned    src;
    size_t      i;

    for (src = 0; src < k->nparts; src++)
    {
        vs_part *from = vs_parts[src];

        if (src == me)
        {
            continue;
        }
        for (i = 0; i < from->nmail[q][me]; i++)
        {
            vs_proc *p = from->mail[q][me][i];

            if (!p->queued)
            {
                p->queued = 1;
                pt->runq[pt->nrun++] = p;
            }
        }
        from->nmail[q][me] = 0;
        for (i = 0; i < from->nxq[q][me]; i++)
        {
            follow_tie(k, me, from->xq[q][me][i].t, from->xq[q][me][i].v, vs_gen, q ^ 1);
        }
        from->nxq[q][me] = 0;
    }
}

/* One of the ties that are waiting leads to another partition (the next round has to be run before the processes). */
static int chain_pending(vs_kernel *k, unsigned q)
{
    unsigned    i, j;
    size_t      e;

    for (i = 0; i < k->nparts; i++)
    {
        for (j = 0; j < k->nparts; j++)
        {
            for (e = 0; i != j && e < vs_parts[i]->nxq[q][j]; e++)
            {
                if (vs_parts[i]->xq[q][j][e].t->chain)
                {
                    return 1;
                }
            }
        }
    }
    return 0;
}

/* Something is left for a partition by the commit of the generation `par` (a parity). */
static int cross_pending(vs_kernel *k, unsigned q)
{
    unsigned    i, j;

    for (i = 0; i < k->nparts; i++)
    {
        for (j = 0; j < k->nparts; j++)
        {
            if (i != j && (vs_parts[i]->nmail[q][j] > 0 || vs_parts[i]->nxq[q][j] > 0))
            {
                return 1;
            }
        }
    }
    return 0;
}

/* The end of a commit round, for all the partitions : the new events are the ones of the next generation. */
static void next_generation(vs_kernel *k)
{
    if (++vs_gen == 0)                  /* wrapped : the stamps of the old events must not match again */
    {
        size_t  j;

        for (j = 0; j < k->nsigs; j++)
        {
            k->sigs[j]->evt = 0;
        }
        vs_gen = 1;
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

/* ------------------------------------------------------------------------------------------------------------------
 * Threads. Partition 0 (the SoC) belongs to the thread that calls vs_settle ; the partitions 1.. (the cores) are
 * shared among the other threads. The delta cycle of vs_settle is the same, with two barriers : after the processes
 * have run (they read the signals that the commit writes) and after the commit (whose last thread prepares the next
 * generation and the run queues). Only POSIX : spin locks (or a mutex and a condition variable when the system has none),
 * sched_yield, no atomics, no affinity. The POSIX rules of memory synchronisation make the lock calls publish the data.
 * ------------------------------------------------------------------------------------------------------------------ */

/* Three barriers, chosen at build time : with -DVS_C11_ATOMICS (ISO C11, not POSIX) one atomic counter and one generation
 * flag, which are much cheaper ; else POSIX spin locks ; else POSIX mutex and condition variable. */
#ifdef VS_C11_ATOMICS
#include <stdatomic.h>
#elif defined(_POSIX_SPIN_LOCKS) && _POSIX_SPIN_LOCKS > 0
#define VS_SPIN 1
#endif

typedef struct vs_barrier
{
#ifdef VS_C11_ATOMICS
    atomic_uint         count;
    char                pad[60];
    atomic_uint         gen;
    unsigned            n;
#elif defined(VS_SPIN)
    pthread_spinlock_t  lock;
#else
    pthread_mutex_t     lock;
    pthread_cond_t      cond;
#endif
#if !defined(VS_C11_ATOMICS)
    unsigned            count, n, gen;
#endif
} vs_barrier;

static void barrier_init(vs_barrier *b, unsigned n)
{
#ifdef VS_C11_ATOMICS
    atomic_init(&b->count, 0);
    atomic_init(&b->gen, 0);
    b->n = n;
    return;
#elif defined(VS_SPIN)
    pthread_spin_init(&b->lock, PTHREAD_PROCESS_PRIVATE);
#else
    pthread_mutex_init(&b->lock, NULL);
    pthread_cond_init(&b->cond, NULL);
#endif
#ifndef VS_C11_ATOMICS
    b->count = 0;
    b->n = n;
    b->gen = 0;
#endif
}

/* The last thread to arrive runs `action` (the others wait) and releases the others. */
static void barrier_wait(vs_barrier *b, void (*action)(void *), void *arg)
{
    unsigned    my, spins = 0;

#ifdef VS_C11_ATOMICS
    my = atomic_load_explicit(&b->gen, memory_order_acquire);
    if (atomic_fetch_add_explicit(&b->count, 1, memory_order_acq_rel) + 1 == b->n)
    {
        atomic_store_explicit(&b->count, 0, memory_order_relaxed);
        if (action != NULL)
        {
            action(arg);
        }
        atomic_store_explicit(&b->gen, my + 1, memory_order_release);
        return;
    }
    while (atomic_load_explicit(&b->gen, memory_order_acquire) == my)
    {
        if (++spins > 20000)
        {
            sched_yield();
            spins = 0;
        }
    }
    return;
#elif defined(VS_SPIN)
    pthread_spin_lock(&b->lock);
    my = b->gen;
    if (++b->count == b->n)
    {
        b->count = 0;
        pthread_spin_unlock(&b->lock);
        if (action != NULL)
        {
            action(arg);
        }
        pthread_spin_lock(&b->lock);
        b->gen++;
        pthread_spin_unlock(&b->lock);
        return;
    }
    pthread_spin_unlock(&b->lock);
    for (;;)
    {
        unsigned    g;

        pthread_spin_lock(&b->lock);
        g = b->gen;
        pthread_spin_unlock(&b->lock);
        if (g != my)
        {
            return;
        }
        if (++spins > 4000)
        {
            sched_yield();              /* more threads than processors : let the others run */
            spins = 0;
        }
    }
#else
    pthread_mutex_lock(&b->lock);
    my = b->gen;
    if (++b->count == b->n)
    {
        b->count = 0;
        pthread_mutex_unlock(&b->lock);
        if (action != NULL)
        {
            action(arg);
        }
        pthread_mutex_lock(&b->lock);
        b->gen++;
        pthread_cond_broadcast(&b->cond);
        pthread_mutex_unlock(&b->lock);
        return;
    }
    while (b->gen == my)
    {
        pthread_cond_wait(&b->cond, &b->lock);
    }
    pthread_mutex_unlock(&b->lock);
    (void) spins;
#endif
}

static struct vs_threads
{
    vs_kernel       *k;
    unsigned        n;                              /* threads, the caller included */
    pthread_t       tid[VS_MAX_PARTS];
    unsigned        parts[VS_MAX_PARTS][VS_MAX_PARTS];
    unsigned        nparts[VS_MAX_PARTS];
    vs_barrier      start, commit_done;
    int             stop;
    int             work, again;
    unsigned        q;                              /* parity of the lists that the threads take */
    int             active;
    int             stats;                          /* VS_STATS : the counters below, one cache line each (no sharing between threads) */
    struct { unsigned long long n; char pad[56]; } delta[VS_MAX_PARTS], runs[VS_MAX_PARTS];
} thr;

static void act_next(void *arg)
{
    vs_kernel   *k = arg;

    if (thr.stats)
    {
        unsigned long long  mx = 0, tot = 0;
        unsigned            t;

        for (t = 0; t < thr.n; t++)
        {
            tot += thr.delta[t].n;
            mx = thr.delta[t].n > mx ? thr.delta[t].n : mx;
            thr.delta[t].n = 0;
        }
        vs_stat_tot += tot;
        vs_stat_max += mx;
    }
    k->deltas++;
    next_generation(k);
    thr.q = vs_gen & 1;
    thr.work = work_left(k) || cross_pending(k, thr.q);
    thr.again = chain_pending(k, thr.q);
}

/* The ties that were followed have left new ones for other partitions (chains) : another round. */
static void act_round(void *arg)
{
    vs_kernel   *k = arg;

    thr.q ^= 1;
    thr.again = cross_pending(k, thr.q);
}

/* The ties and the woken processes that the others left for the partitions of thread `me`, round after round. */
static void take_incoming(unsigned me)
{
    vs_kernel   *k = thr.k;
    unsigned    j;

    for (j = 0; j < thr.nparts[me]; j++)
    {
        apply_incoming(k, thr.parts[me][j], thr.q);
    }
    while (thr.again)
    {
        barrier_wait(&thr.commit_done, act_round, k);
        if (!thr.again)
        {
            break;
        }
        for (j = 0; j < thr.nparts[me]; j++)
        {
            apply_incoming(k, thr.parts[me][j], thr.q);
        }
    }
}

/* One delta cycle, as vs_settle does it, but for the partitions of thread `me` and with one barrier : once every thread has run
 * its processes and committed, each takes what the others left for it (the processes they woke, the ties that reach it) before
 * it runs the next delta. A thread that is still taking does not disturb one that has begun to run : they write and read
 * the signals of their own partitions only. */
static void thread_settle(unsigned me)
{
    vs_kernel   *k = thr.k;
    unsigned    j;
    size_t      i;

    for (j = 0; j < thr.nparts[me]; j++)
    {
        commit(k, thr.parts[me][j]);
    }
    barrier_wait(&thr.commit_done, act_next, k);
    take_incoming(me);
    while (thr.work)
    {
        unsigned long long  ran = 0;

        for (j = 0; j < thr.nparts[me]; j++)
        {
            vs_part *pt = vs_parts[thr.parts[me][j]];
            size_t  n = pt->nrun;

            pt->nrun = 0;
            if (thr.stats)
            {
                thr.runs[thr.parts[me][j]].n += n;
                ran += n;
            }
            for (i = 0; i < n; i++)
            {
                vs_proc *p = pt->runq[i];

                p->queued = 0;
                p->run(p->inst);
            }
        }
        thr.delta[me].n = ran;
        for (j = 0; j < thr.nparts[me]; j++)
        {
            commit(k, thr.parts[me][j]);
        }
        barrier_wait(&thr.commit_done, act_next, k);
        take_incoming(me);
    }
}

static void *worker_main(void *arg)
{
    unsigned    me = (unsigned) (uintptr_t) arg;

    for (;;)
    {
        barrier_wait(&thr.start, NULL, NULL);
        if (thr.stop)
        {
            break;
        }
        thread_settle(me);
    }
    return NULL;
}

int vs_threads_start(vs_kernel *k, unsigned n)
{
    unsigned    p, t;

    if (n < 2 || k->nparts < 2 || thr.active)
    {
        return 0;
    }
    if (n - 1 > k->nparts - 1)
    {
        n = k->nparts;                              /* no more threads than partitions */
    }
    memset(&thr, 0, sizeof(thr));
    thr.k = k;
    thr.n = n;
    thr.nparts[0] = 1;                              /* the caller runs partition 0 */
    thr.parts[0][0] = 0;
    for (p = 1; p < k->nparts; p++)
    {
        t = 1 + (p - 1) % (n - 1);
        thr.parts[t][thr.nparts[t]++] = p;
    }
    thr.stats = getenv("VS_STATS") != NULL;
    if (thr.stats)
    {
        for (t = 0; t < n; t++)
        {
            unsigned j;

            fprintf(stderr, "thread %u runs the partitions", t);
            for (j = 0; j < thr.nparts[t]; j++)
            {
                fprintf(stderr, " %u", thr.parts[t][j]);
            }
            fprintf(stderr, "\n");
        }
    }
    barrier_init(&thr.start, n);
    barrier_init(&thr.commit_done, n);
    for (t = 1; t < n; t++)
    {
        if (pthread_create(&thr.tid[t], NULL, worker_main, (void *) (uintptr_t) t) != 0)
        {
            return -1;                              /* (the threads already created wait at the barrier : not handled) */
        }
    }
    thr.active = 1;
    return 0;
}

void vs_threads_stop(vs_kernel *k)
{
    unsigned    t;

    if (!thr.active)
    {
        return;
    }
    thr.stop = 1;
    barrier_wait(&thr.start, NULL, NULL);
    for (t = 1; t < thr.n; t++)
    {
        pthread_join(thr.tid[t], NULL);
    }
    if (thr.stats)
    {
        unsigned p;

        for (p = 0; p < k->nparts; p++)
        {
            vs_stat_runs[p] += thr.runs[p].n;
        }
    }
    thr.active = 0;
}

static uint64_t settle_threads(vs_kernel *k)
{
    uint64_t    start = k->deltas;

    barrier_wait(&thr.start, NULL, NULL);
    thread_settle(0);
    return k->deltas - start;
}

uint64_t vs_settle(vs_kernel *k)
{
    uint64_t    start = k->deltas;
    size_t      i;
    unsigned    pi, qa;

    if (!k->finalised)
    {
        finalise(k);
    }
    if (thr.active && k->initialised)
    {
        return settle_threads(k);
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
    qa = vs_gen & 1;
    do
    {
        for (pi = 0; pi < k->nparts; pi++)
        {
            apply_incoming(k, pi, qa);
        }
        qa ^= 1;
    }
    while (cross_pending(k, qa));

    while (work_left(k))
    {
        /* Processes see the events of the previous commit while they run. Nothing is queued while they run (queueing is
         * done by commit), so the flag of a process can be cleared just before it runs. */
        {
            size_t  mx = 0, tot = 0;

            for (pi = 0; pi < k->nparts; pi++)
            {
                size_t  n = vs_parts[pi]->nrun;

                tot += n;
                mx = n > mx ? n : mx;
            }
            vs_stat_max += mx;
            vs_stat_tot += tot;
        }
        for (pi = 0; pi < k->nparts; pi++)
        {
            vs_part *pt = vs_parts[pi];
            size_t  n = pt->nrun;

            pt->nrun = 0;
            vs_stat_runs[pi] += n;
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
        qa = vs_gen & 1;
        do
        {
            for (pi = 0; pi < k->nparts; pi++)
            {
                apply_incoming(k, pi, qa);
            }
            qa ^= 1;
        }
        while (cross_pending(k, qa));
    }
    return k->deltas - start;
}
