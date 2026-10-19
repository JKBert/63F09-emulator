#include "hand/obuf.h"

static void obuf_run(void *inst)
{
    obuf_t  *self = inst;

    vs_drive(self->o, self->i->cur);
}

void obuf_create(vs_kernel *k, obuf_t *self, const char *path, vs_sig *i, vs_sig *o)
{
    vs_sig  *sens[1];

    (void) path;
    self->i = i;
    self->o = o;
    sens[0] = i;
    vs_register_process(k, obuf_run, self, sens, 1);
}
