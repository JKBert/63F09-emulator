#include "hand/ramcore.h"

static void ramcore_run(void *inst)
{
    ramcore_t   *self = inst;
    uint8_t     mask = (uint8_t) ((1u << self->bits) - 1);
    int         p;

    for (p = 0; p < 2; p++)
    {
        if (vs_rising(self->clk[p]) && (self->en[p] == NULL || self->en[p]->cur == 1))
        {
            unsigned    a = (unsigned) (self->addr[p]->cur & 0xFFFF);

            /* READ_FIRST : the latch gets the old content, then the write happens */
            self->out[p][a >> 14] = self->mem[a];
            if (self->rw[p]->cur == 1)
            {
                self->mem[a] = (uint8_t) (self->din[p]->cur & mask);
            }
        }
    }
    for (p = 0; p < 2; p++)
    {
        vs_drive(self->dout[p], self->out[p][(self->addr[p]->cur >> 14) & 3]);
    }
}

void ramcore_create(vs_kernel *k, ramcore_t *self, const char *path, unsigned bits, vs_sig *clk, vs_sig *rw, vs_sig *addr, vs_sig *din,
                    vs_sig *dout, vs_sig *en, vs_sig *clk2, vs_sig *rw2, vs_sig *addr2, vs_sig *din2, vs_sig *dout2,
                    vs_sig *en2)
{
    vs_sig  *sens[4];

    self->bits = bits;
    self->mem = vs_alloc(k, 65536);
    vs_region_add(k, path, self->mem, 65536);
    self->clk[0] = clk;
    self->rw[0] = rw;
    self->addr[0] = addr;
    self->din[0] = din;
    self->dout[0] = dout;
    self->en[0] = en;
    self->clk[1] = clk2;
    self->rw[1] = rw2;
    self->addr[1] = addr2;
    self->din[1] = din2;
    self->dout[1] = dout2;
    self->en[1] = en2;
    sens[0] = clk;
    sens[1] = clk2;
    sens[2] = addr;
    sens[3] = addr2;
    vs_register_process(k, ramcore_run, self, sens, 4);
}

uint8_t *ramcore_data(ramcore_t *self)
{
    return self->mem;
}
