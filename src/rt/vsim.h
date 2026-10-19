/*
 * vsim : minimal VHDL signal semantics for the generated C.
 *
 * A signal holds a current and a next value. Processes read current values and write next
 * values ; at the end of a delta cycle every pending value is committed and the signals that
 * changed raise an event. The processes sensitive to those events run in the next delta
 * cycle. The simulation is quiescent when a delta cycle commits no change.
 *
 * One simulation per program : the list of pending signals is shared by vs_drive().
 */

#ifndef VSIM_H
#define VSIM_H

#include <stddef.h>
#include <stdint.h>

struct vs_proc;

typedef struct vs_sig
{
    uint64_t        cur;
    uint64_t        nxt;
    uint8_t         pend;
    uint8_t         evt;
    struct vs_proc  **fan;      /* processes woken by an event on this signal */
    uint32_t        nfan;
} vs_sig;

typedef struct vs_proc
{
    void            (*run)(void *inst);
    void            *inst;
    vs_sig          **sens;
    size_t          nsens;
    uint8_t         queued;
} vs_proc;

typedef struct vs_kernel
{
    vs_sig          **sigs;
    size_t          nsigs, csigs;
    vs_proc         **procs;
    size_t          nprocs, cprocs;
    vs_proc         **runq;
    size_t          nrun;
    vs_sig          **events;
    size_t          nevents;
    uint64_t        deltas;
    int             initialised;
    int             finalised;
} vs_kernel;

extern vs_sig   **vs_pendlist;
extern size_t   vs_npend;

void    vs_kernel_init(vs_kernel *k);
void    vs_kernel_free(vs_kernel *k);

/* Registration, done while the design is built. */
void    vs_register_signal(vs_kernel *k, vs_sig *s, uint64_t init);
void    vs_register_process(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, size_t nsens);

/* Run delta cycles until nothing changes. Returns the number of delta cycles executed. */
uint64_t vs_settle(vs_kernel *k);

/* Schedule a value on a signal, from a process or from the test bench. */
static inline void vs_drive(vs_sig *s, uint64_t v)
{
    s->nxt = v;
    if (!s->pend)
    {
        s->pend = 1;
        vs_pendlist[vs_npend++] = s;
    }
}

static inline int vs_rising(const vs_sig *s)
{
    return s->evt && s->cur == 1;
}

static inline int vs_falling(const vs_sig *s)
{
    return s->evt && s->cur == 0;
}

#endif
