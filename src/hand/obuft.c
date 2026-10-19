#include "hand/obuft.h"

static void obuft_run(void *inst)
{
    obuft_t *self = inst;

    if (self->t->cur == 0)
    {
        vs_drive(self->o, self->i->cur);
    }
}

void obuft_create(vs_kernel *k, obuft_t *self, const char *path, vs_sig *i, vs_sig *o, vs_sig *t)
{
    vs_sig  *sens[2];

    (void) path;
    self->i = i;
    self->o = o;
    self->t = t;
    sens[0] = i;
    sens[1] = t;
    vs_register_process(k, obuft_run, self, sens, 2);
}
