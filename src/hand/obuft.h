/* OBUFT : output buffer with tri-state. O follows I when T is 0 ; when T is 1 the pad is released and keeps the last
 * value (a two-valued simulation has no high impedance). */

#ifndef HAND_OBUFT_H
#define HAND_OBUFT_H

#include "vsim.h"

typedef struct obuft_t
{
    vs_sig  *i, *o, *t;
} obuft_t;

void obuft_create(vs_kernel *k, obuft_t *self, const char *path, vs_sig *i, vs_sig *o, vs_sig *t);

#endif
