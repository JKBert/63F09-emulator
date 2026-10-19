#include "hand/plle2_base.h"

typedef struct pll_out
{
    plle2_base_t    *pll;
    vs_sig          *s;
    int64_t         div;
    uint64_t        n;          /* half periods generated so far */
} pll_out;

/* Time of the n-th half period of an output : exact, rounded down. */
static uint64_t pll_time(const plle2_base_t *p, int64_t div, uint64_t n)
{
    return p->first + (uint64_t) (((unsigned __int128) n * p->period * (uint64_t) p->divclk * (uint64_t) div) /
                                  ((unsigned __int128) 2 * (uint64_t) p->mult));
}

static void pll_edge(vs_kernel *k, void *arg)
{
    pll_out *o = arg;

    vs_drive(o->s, o->s->cur ^ 1);
    o->n++;
    vs_timer_add(k, pll_time(o->pll, o->div, o->n), pll_edge, o);
}

static void pll_locked(vs_kernel *k, void *arg)
{
    plle2_base_t    *p = arg;

    (void) k;
    vs_drive(p->locked, 1);
}

/* The CLKIN1 edges are seen by a process ; it needs the kernel to add timers. */
typedef struct pll_watch
{
    vs_kernel       *k;
    plle2_base_t    *pll;
    pll_out         out[2];
    uint64_t        seen;
} pll_watch;

static void pll_watch_run(void *inst)
{
    pll_watch       *w = inst;
    plle2_base_t    *p = w->pll;
    vs_kernel       *k = w->k;

    if (!vs_rising(p->clkin1))
    {
        return;
    }
    if (w->seen == 0)
    {
        p->first = k->now;
    }
    else if (w->seen == 1)
    {
        int i;

        p->period = k->now - p->first;
        for (i = 0; i < 2; i++)
        {
            w->out[i].pll = p;
            w->out[i].s = i == 0 ? p->clkout0 : p->clkout1;
            w->out[i].div = i == 0 ? p->div0 : p->div1;
            w->out[i].n = 0;
            /* the outputs start on the first CLKIN1 edge that follows the measure */
            vs_timer_add(k, k->now, pll_edge, &w->out[i]);
        }
        p->first = k->now;
        vs_timer_add(k, k->now + p->period * PLL_LOCK_CYCLES, pll_locked, p);
    }
    w->seen++;
}

void plle2_base_create(vs_kernel *k, plle2_base_t *self, const char *path, int64_t clkfbout_mult, int64_t clkout0_divide,
                       int64_t clkout1_divide, int64_t divclk_divide, vs_sig *clkfbin, vs_sig *clkin1,
                       vs_sig *pwrdwn, vs_sig *rst, vs_sig *clkfbout, vs_sig *clkout0, vs_sig *clkout1, vs_sig *locked)
{
    pll_watch   *w = vs_alloc(k, sizeof(*w));
    vs_sig      *sens[1];

    (void) path;
    self->mult = clkfbout_mult;
    self->divclk = divclk_divide;
    self->div0 = clkout0_divide;
    self->div1 = clkout1_divide;
    self->clkfbin = clkfbin;
    self->clkin1 = clkin1;
    self->pwrdwn = pwrdwn;
    self->rst = rst;
    self->clkfbout = clkfbout;
    self->clkout0 = clkout0;
    self->clkout1 = clkout1;
    self->locked = locked;
    w->k = k;
    w->pll = self;
    sens[0] = clkin1;
    vs_register_process(k, pll_watch_run, w, sens, 1);
}
