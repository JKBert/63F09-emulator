/* BUFGCTRL : clock multiplexer. The 63F09 sources use it with the clock enables and the IGNOREx inputs tied to '1' and the
 * two selects S0 / S1 complementary, driven by a register that only changes while the clocks are idle : S1 selects I1, else S0
 * selects I0, else the previous selection is kept (initially I0). The glitch-free switching of the real primitive is not modelled. */

#ifndef HAND_BUFGCTRL_H
#define HAND_BUFGCTRL_H

#include "vsim.h"

typedef struct bufgctrl_t
{
    vs_sig  *ce0, *ce1, *i0, *i1, *ignore0, *ignore1, *s0, *s1, *o;
    int     sel1;
} bufgctrl_t;

void bufgctrl_create(vs_kernel *k, bufgctrl_t *self, const char *path, vs_sig *ce0, vs_sig *ce1, vs_sig *i0, vs_sig *i1,
                     vs_sig *ignore0, vs_sig *ignore1, vs_sig *s0, vs_sig *s1, vs_sig *o);

#endif
