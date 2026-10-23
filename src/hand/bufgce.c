#include "hand/bufgce.h"

/* The latch follows CE while I is low, and keeps its value while I is high. */
static void bufgce_latch(void *inst)
{
    bufgce_t    *self = inst;

    if (self->i->cur == 0)
    {
        vs_drive(&self->latch, self->ce->cur);
    }
}

static void bufgce_run(void *inst)
{
    bufgce_t    *self = inst;

    vs_drive(self->o, self->i->cur & self->latch.cur);
}

void bufgce_create(vs_kernel *k, bufgce_t *self, const char *path, vs_sig *ce, vs_sig *i, vs_sig *o)
{
    vs_sig  *sens[2];

    (void) path;
    self->ce = ce;
    self->i = i;
    self->o = o;
    vs_register_signal(k, &self->latch, 0);
    sens[0] = ce;
    sens[1] = i;
    vs_register_process(k, bufgce_latch, self, sens, 2);
    sens[0] = i;
    sens[1] = &self->latch;
    vs_register_process(k, bufgce_run, self, sens, 2);
}
