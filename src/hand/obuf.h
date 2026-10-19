/* OBUF : output buffer. O follows I one delta cycle later, as in the UNISIM model. */

#ifndef HAND_OBUF_H
#define HAND_OBUF_H

#include "vsim.h"

typedef struct obuf_t
{
    vs_sig  *i, *o;
} obuf_t;

void obuf_create(vs_kernel *k, obuf_t *self, const char *path, vs_sig *i, vs_sig *o);

#endif
