#include "hand/bufgctrl.h"

static void bufgctrl_run(void *inst)
{
    bufgctrl_t  *self = inst;

    if (self->s1->cur && self->ce1->cur)
    {
        self->sel1 = 1;
    }
    else if (self->s0->cur && self->ce0->cur)
    {
        self->sel1 = 0;
    }
    vs_drive(self->o, self->sel1 ? self->i1->cur : self->i0->cur);
}

void bufgctrl_create(vs_kernel *k, bufgctrl_t *self, const char *path, vs_sig *ce0, vs_sig *ce1, vs_sig *i0, vs_sig *i1,
                     vs_sig *ignore0, vs_sig *ignore1, vs_sig *s0, vs_sig *s1, vs_sig *o)
{
    vs_sig  *sens[6];

    (void) path;
    self->ce0 = ce0;
    self->ce1 = ce1;
    self->i0 = i0;
    self->i1 = i1;
    self->ignore0 = ignore0;
    self->ignore1 = ignore1;
    self->s0 = s0;
    self->s1 = s1;
    self->o = o;
    self->sel1 = 0;
    sens[0] = i0;
    sens[1] = i1;
    sens[2] = s0;
    sens[3] = s1;
    sens[4] = ce0;
    sens[5] = ce1;
    vs_register_process(k, bufgctrl_run, self, sens, 6);
}
