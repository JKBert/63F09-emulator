#include <string.h>

#include "hand/rom_27f512.h"

static void rom_27f512_run(void *inst)
{
    rom_27f512_t    *self = inst;

    if (vs_rising(self->clock) && self->enable->cur == 1)
    {
        self->latch = self->mem[self->address->cur & 0xFFFF];
    }
    vs_drive(self->mrdy, 1);
    vs_drive(self->data_output, self->enable->cur == 1 ? self->latch : 0xFF);
}

void rom_27f512_create(vs_kernel *k, rom_27f512_t *self, const char *path, vs_sig *clock, vs_sig *rom_enable,
                       vs_sig *address, vs_sig *data_output, vs_sig *mrdy)
{
    vs_sig  *sens[3];

    self->mem = vs_alloc(k, 65536);
    memset(self->mem, 0xFF, 65536);
    self->latch = 0;
    self->clock = clock;
    self->enable = rom_enable;
    self->address = address;
    self->data_output = data_output;
    self->mrdy = mrdy;
    vs_region_add(k, path, self->mem, 65536);
    sens[0] = clock;
    sens[1] = rom_enable;
    sens[2] = address;
    vs_register_process(k, rom_27f512_run, self, sens, 3);
}
