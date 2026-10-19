#include "hand/iobuf.h"

static void iobuf_drive(void *inst)
{
    iobuf_t *self = inst;

    if (self->t->cur == 0)
    {
        vs_drive(self->io, self->i->cur);
    }
}

static void iobuf_read(void *inst)
{
    iobuf_t *self = inst;

    vs_drive(self->o, self->io->cur);
}

void iobuf_create(vs_kernel *k, iobuf_t *self, const char *path, vs_sig *i, vs_sig *io, vs_sig *o, vs_sig *t)
{
    vs_sig  *sens[2];

    (void) path;
    self->i = i;
    self->io = io;
    self->o = o;
    self->t = t;
    sens[0] = i;
    sens[1] = t;
    vs_register_process(k, iobuf_drive, self, sens, 2);
    sens[0] = io;
    vs_register_process(k, iobuf_read, self, sens, 1);
}
