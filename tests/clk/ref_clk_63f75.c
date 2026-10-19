#include "ref_clk_63f75.h"

/* process(RESET_n, TICK) */
static void clk_63f75_p0(void *inst)
{
    clk_63f75   *self = inst;

    if (self->reset_n->cur == 0)
    {
        vs_drive(&self->position, 0x1);
        vs_drive(self->e, 0);
        vs_drive(self->q, 1);
        vs_drive(self->c, 1);
    }
    else if (vs_rising(self->tick))
    {
        if (self->mrdy->cur == 1)
        {
            uint64_t    p = self->position.cur;

            /* POSITION(2 downto 0) & POSITION(3) */
            vs_drive(&self->position, ((p & 0x7) << 1) | ((p >> 3) & 1));
            vs_drive(self->e, (p & 1) | ((p >> 1) & 1));
            vs_drive(self->q, ((p >> 3) & 1) | (p & 1));
            vs_drive(self->c, ~((p & 1) | ((p >> 1) & 1)) & 1);
        }
    }
}

void clk_63f75_create(vs_kernel *k, clk_63f75 *self,
                      vs_sig *reset_n, vs_sig *mrdy, vs_sig *tick,
                      vs_sig *e, vs_sig *q, vs_sig *c)
{
    vs_sig  *sens[2];

    self->reset_n = reset_n;
    self->mrdy = mrdy;
    self->tick = tick;
    self->e = e;
    self->q = q;
    self->c = c;
    vs_register_signal(k, &self->position, 0x1);
    sens[0] = reset_n;
    sens[1] = tick;
    vs_register_process(k, clk_63f75_p0, self, sens, 2);
}
