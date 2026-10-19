/* BUFG : global clock buffer. As in the UNISIM model, O follows I one delta cycle later. */

#ifndef HAND_BUFG_H
#define HAND_BUFG_H

#include "vsim.h"

typedef struct bufg_t
{
    vs_sig  *i, *o;
} bufg_t;

void bufg_create(vs_kernel *k, bufg_t *self, const char *path, vs_sig *i, vs_sig *o);

#endif
