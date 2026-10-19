#include <stdlib.h>
#include <string.h>

#include "vsim.h"

vs_sig  **vs_pendlist;
size_t  vs_npend;

static void *xrealloc(void *p, size_t n)
{
    p = realloc(p, n ? n : 1);
    if (p == NULL)
    {
        abort();
    }
    return p;
}

void vs_kernel_init(vs_kernel *k)
{
    memset(k, 0, sizeof(*k));
    vs_npend = 0;
}

void vs_kernel_free(vs_kernel *k)
{
    size_t  i;

    for (i = 0; i < k->nsigs; i++)
    {
        free(k->sigs[i]->fan);
        k->sigs[i]->fan = NULL;
        k->sigs[i]->nfan = 0;
    }
    for (i = 0; i < k->nprocs; i++)
    {
        free(k->procs[i]->sens);
        free(k->procs[i]);
    }
    free(k->sigs);
    free(k->procs);
    free(k->runq);
    free(k->events);
    free(vs_pendlist);
    vs_pendlist = NULL;
    vs_npend = 0;
    memset(k, 0, sizeof(*k));
}

void vs_register_signal(vs_kernel *k, vs_sig *s, uint64_t init)
{
    s->cur = init;
    s->nxt = init;
    s->pend = 0;
    s->evt = 0;
    s->fan = NULL;
    s->nfan = 0;
    if (k->nsigs == k->csigs)
    {
        k->csigs = k->csigs ? k->csigs * 2 : 256;
        k->sigs = xrealloc(k->sigs, k->csigs * sizeof(*k->sigs));
    }
    k->sigs[k->nsigs++] = s;
}

void vs_register_process(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, size_t nsens)
{
    vs_proc *p = xrealloc(NULL, sizeof(*p));

    p->run = run;
    p->inst = inst;
    p->nsens = nsens;
    p->queued = 0;
    p->sens = xrealloc(NULL, nsens * sizeof(*p->sens));
    memcpy(p->sens, sens, nsens * sizeof(*p->sens));
    if (k->nprocs == k->cprocs)
    {
        k->cprocs = k->cprocs ? k->cprocs * 2 : 256;
        k->procs = xrealloc(k->procs, k->cprocs * sizeof(*k->procs));
    }
    k->procs[k->nprocs++] = p;
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
            vs_sig  *s = p->sens[j];
            size_t  m;
            int     dup = 0;

            for (m = 0; m < s->nfan; m++)
            {
                if (s->fan[m] == p)
                {
                    dup = 1;
                    break;
                }
            }
            if (!dup)
            {
                s->fan = xrealloc(s->fan, (s->nfan + 1) * sizeof(*s->fan));
                s->fan[s->nfan++] = p;
            }
        }
    }
    k->runq = xrealloc(NULL, k->nprocs * sizeof(*k->runq));
    k->events = xrealloc(NULL, k->nsigs * sizeof(*k->events));
    vs_pendlist = xrealloc(vs_pendlist, k->nsigs * sizeof(*vs_pendlist));
    k->finalised = 1;
}

/* Commit the pending values : raises the events and queues the processes they wake. */
static void commit(vs_kernel *k)
{
    size_t  i;

    k->nevents = 0;
    for (i = 0; i < vs_npend; i++)
    {
        vs_sig  *s = vs_pendlist[i];

        s->pend = 0;
        if (s->nxt != s->cur)
        {
            uint32_t    m;

            s->cur = s->nxt;
            s->evt = 1;
            k->events[k->nevents++] = s;
            for (m = 0; m < s->nfan; m++)
            {
                vs_proc *p = s->fan[m];

                if (!p->queued)
                {
                    p->queued = 1;
                    k->runq[k->nrun++] = p;
                }
            }
        }
    }
    vs_npend = 0;
}

static void clear_events(vs_kernel *k)
{
    size_t  i;

    for (i = 0; i < k->nevents; i++)
    {
        k->events[i]->evt = 0;
    }
    k->nevents = 0;
}

uint64_t vs_settle(vs_kernel *k)
{
    uint64_t    start = k->deltas;
    size_t      i;

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
    commit(k);

    while (k->nrun > 0)
    {
        size_t  n = k->nrun;

        k->nrun = 0;
        for (i = 0; i < n; i++)
        {
            k->runq[i]->queued = 0;
        }
        /* Processes see the events of the previous commit while they run. */
        for (i = 0; i < n; i++)
        {
            k->runq[i]->run(k->runq[i]->inst);
        }
        clear_events(k);
        k->deltas++;
        commit(k);
    }
    clear_events(k);
    return k->deltas - start;
}
