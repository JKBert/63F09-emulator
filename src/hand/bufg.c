#include "hand/bufg.h"

static void bufg_run(void *inst)
{
    bufg_t  *self = inst;

    vs_drive(self->o, self->i->cur);
}

void bufg_create(vs_kernel *k, bufg_t *self, const char *path, vs_sig *i, vs_sig *o)
{
    vs_sig  *sens[1];

    (void) path;
    self->i = i;
    self->o = o;
    sens[0] = i;
    vs_register_process(k, bufg_run, self, sens, 1);
}
