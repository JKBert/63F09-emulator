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
#include <stdio.h>

struct vs_proc;
struct vs_sig;

/* Zero-delay link of a field of a signal to a field of another one : used when a port is connected
 * to a part of a signal (a slice, an element). The destination follows the source in the same
 * delta cycle, as the two are one net in VHDL. */
typedef struct vs_tie
{
    struct vs_sig   *dst;
    unsigned        dst_shift, src_shift;
    uint64_t        mask;           /* unshifted mask of the field */
} vs_tie;

typedef struct vs_sig
{
    uint64_t        cur;
    uint64_t        nxt;
    uint64_t        prev;       /* value before the event of this delta */
    uint64_t        pulled;     /* bits that the outside world pulls low (open-drain pads) : cur = nxt & ~pulled */
    uint8_t         wand;       /* a pad whose drivers are wired-AND : a released IOBUF drives ones */
    uint8_t         pend;
    uint8_t         evt;
    struct vs_fan   *fan;       /* processes woken by an event on this signal */
    uint32_t        nfan;
    const char      *name;      /* for the traces, NULL when unnamed */
    uint32_t        width;
    uint64_t        last;       /* value at the last dump */
    uint8_t         dumped;
    vs_tie          *ties;      /* nets that follow this signal */
    uint32_t        nties;
} vs_sig;

/* A process woken by a signal, and the bits whose events it is sensitive to (a bit of a vector in a sensitivity list). */
typedef struct vs_fan
{
    struct vs_proc  *p;
    uint64_t        mask;
} vs_fan;

typedef struct vs_proc
{
    void            (*run)(void *inst);
    void            *inst;
    vs_sig          **sens;
    uint64_t        *masks;     /* per entry of sens, NULL : all the bits */
    size_t          nsens;
    uint8_t         queued;
} vs_proc;

struct vs_kernel;

/* A callback at a given time : the clock sources and the PLL are made of them. */
typedef struct vs_timer
{
    uint64_t        when;
    void            (*fn)(struct vs_kernel *k, void *arg);
    void            *arg;
} vs_timer;

/* A memory that the host can load or inspect (ROM, RAM) : registered by its model under the path of its instance. */
typedef struct vs_region
{
    const char  *path;
    uint8_t     *data;
    size_t      size;
} vs_region;

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
    char            **names;
    size_t          nnames, cnames;
    void            **allocs;
    size_t          nallocs, callocs;
    uint64_t        deltas;
    vs_region       *regions;
    size_t          nregions, cregions;
    uint64_t        now;        /* simulated time, in ticks */
    vs_timer        *timers;    /* sorted by time */
    size_t          ntimers, ctimers;
    int             initialised;
    int             finalised;
} vs_kernel;

extern vs_sig   **vs_pendlist;
extern size_t   vs_npend;

void    vs_kernel_init(vs_kernel *k);
void    vs_kernel_free(vs_kernel *k);

/* Links a field of `src` to a field of `dst` (see vs_tie). The destination takes the current value. */
void    vs_tie_fields(vs_sig *src, unsigned src_shift, vs_sig *dst, unsigned dst_shift, unsigned width);

/* All the memory of a run comes from one arena at a fixed address (see vsim.c) : a snapshot is its content. vs_arena_alloc
 * returns zeroed memory. */
int     vs_arena_map(void);
void    *vs_arena_alloc(size_t n);
void    vs_arena_region(void **base, size_t *used);
void    vs_arena_set_used(size_t used);

/* Memory that lives as long as the kernel. */
void    *vs_alloc(vs_kernel *k, size_t size);

/* Names a signal for the traces. `name` is copied. */
void    vs_name(vs_kernel *k, vs_sig *s, const char *path, const char *name, unsigned width);

/* Instance path : "<a>.<b>", kept by the kernel (valid until vs_kernel_free). */
const char *vs_join(vs_kernel *k, const char *a, const char *b);

/* Writes "<phase> <name> <value>" for every named signal that changed since the last call. */
void    vs_dump(vs_kernel *k, FILE *f, long phase);

/* Registration, done while the design is built. */
void    vs_register_signal(vs_kernel *k, vs_sig *s, uint64_t init);
void    vs_register_process_masked(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, const uint64_t *masks, size_t nsens);
void    vs_register_process(vs_kernel *k, void (*run)(void *), void *inst, vs_sig **sens, size_t nsens);

/* Timed callbacks. vs_advance moves the time to the earliest timer, runs the timers due then and settles the
 * design ; it returns 0 when no timer is left. */
void    vs_timer_add(vs_kernel *k, uint64_t when, void (*fn)(vs_kernel *, void *), void *arg);
int     vs_advance(vs_kernel *k);

/* The outside world pulls the bits of `mask` of a pad low (`low` = 1) or lets them go (`low` = 0). */
void    vs_pull(vs_sig *s, uint64_t mask, int low);

/* Memories. vs_region_find returns the first region whose path ends with `suffix`, or NULL. */
void    vs_region_add(vs_kernel *k, const char *path, uint8_t *data, size_t size);
vs_region *vs_region_find(vs_kernel *k, const char *suffix);

/* A square wave on `s`: the signal rises at `first` and toggles every `half` ticks. */
void    vs_clock_source(vs_kernel *k, vs_sig *s, uint64_t first, uint64_t half);

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

/* A reference to some bits of a signal : what a signal parameter is when its actual is a part of a vector. */
typedef struct vs_ref
{
    vs_sig      *s;
    unsigned    shift;
    uint64_t    mask;
} vs_ref;

static inline vs_ref vs_mkref(vs_sig *s, unsigned shift, unsigned width)
{
    vs_ref r;

    r.s = s;
    r.shift = shift;
    r.mask = width >= 64 ? UINT64_MAX : (UINT64_C(1) << width) - 1;
    return r;
}

static inline uint64_t vs_ref_get(vs_ref r)
{
    return (r.s->cur >> r.shift) & r.mask;
}

/* Set by the VHDL procedure "finish" : the simulation must stop. */
extern int vs_finished;

/* Schedule a value on some bits of a signal : `mask` is the unshifted mask of the field. */
static inline void vs_drive_bits(vs_sig *s, unsigned shift, uint64_t mask, uint64_t v)
{
    uint64_t m = mask << shift;

    vs_drive(s, (s->nxt & ~m) | ((v << shift) & m));
}

static inline void vs_ref_drive(vs_ref r, uint64_t v)
{
    vs_drive_bits(r.s, r.shift, r.mask, v);
}

static inline void vs_ref_drive_bits(vs_ref r, unsigned shift, uint64_t mask, uint64_t v)
{
    vs_drive_bits(r.s, r.shift + shift, mask, v);
}

static inline int vs_rising(const vs_sig *s)
{
    return s->evt && s->cur == 1;
}

static inline int vs_falling(const vs_sig *s)
{
    return s->evt && s->cur == 0;
}

static inline int vs_rising_bit(const vs_sig *s, unsigned pos)
{
    return s->evt && ((s->prev >> pos) & 1) == 0 && ((s->cur >> pos) & 1) == 1;
}

static inline int vs_falling_bit(const vs_sig *s, unsigned pos)
{
    return s->evt && ((s->prev >> pos) & 1) == 1 && ((s->cur >> pos) & 1) == 0;
}

#endif
