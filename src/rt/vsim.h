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

/* Helpers of the generated code. */

/* Sign extension of a w-bit value (1 <= w <= 64). */
static inline int64_t vs_sext(uint64_t v, unsigned w)
{
    return (int64_t) (v << (64 - w)) >> (64 - w);
}

/* VHDL "mod" : the result has the sign of the divisor. */
static inline int64_t vs_mod(int64_t a, int64_t b)
{
    int64_t r = a % b;

    return (r != 0 && ((r < 0) != (b < 0))) ? r + b : r;
}

static inline int64_t vs_ipow(int64_t a, int64_t n)
{
    int64_t r = 1;

    while (n-- > 0)
    {
        r *= a;
    }
    return r;
}

static inline uint64_t vs_shl(uint64_t v, int64_t n)
{
    return (n < 0 || n >= 64) ? 0 : v << n;
}

static inline uint64_t vs_shr(uint64_t v, int64_t n)
{
    return (n < 0 || n >= 64) ? 0 : v >> n;
}

static inline uint64_t vs_parity(uint64_t v)
{
    v ^= v >> 32;
    v ^= v >> 16;
    v ^= v >> 8;
    v ^= v >> 4;
    v ^= v >> 2;
    v ^= v >> 1;
    return v & 1;
}

/* Set by the VHDL procedure "finish" : the simulation must stop. */
extern int vs_finished;

/* Schedule a value on some bits of a signal. */
static inline void vs_drive_bits(vs_sig *s, unsigned shift, uint64_t mask, uint64_t v)
{
    vs_drive(s, (s->nxt & ~mask) | ((v << shift) & mask));
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
