#include "hand/ram_61f32x64.h"

static void ram_61f32x64_run(void *inst)
{
    ram_61f32x64_t  *self = inst;

    if (vs_rising(self->rdclk))
    {
        self->out = self->mem[self->rdaddr->cur & 511];
    }
    if (vs_rising(self->wrclk) && self->we->cur == 1)
    {
        self->mem[self->wraddr->cur & 511] = self->din->cur;
    }
    vs_drive(self->dout, self->out);
}

void ram_61f32x64_create(vs_kernel *k, ram_61f32x64_t *self, const char *path, vs_sig *rdclk, vs_sig *wrclk,
                         vs_sig *we, vs_sig *rdaddr, vs_sig *wraddr, vs_sig *data_in, vs_sig *data_out)
{
    vs_sig  *sens[2];

    (void) path;
    self->mem = vs_alloc(k, 512 * sizeof(uint64_t));
    self->out = 0;
    self->rdclk = rdclk;
    self->wrclk = wrclk;
    self->we = we;
    self->rdaddr = rdaddr;
    self->wraddr = wraddr;
    self->din = data_in;
    self->dout = data_out;
    sens[0] = rdclk;
    sens[1] = wrclk;
    vs_register_process(k, ram_61f32x64_run, self, sens, 2);
}
