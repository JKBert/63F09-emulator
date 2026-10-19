/* IOBUF : bidirectional buffer. IO is driven by I when T is 0 and released when T is 1 ; O follows IO.
 * A released pad keeps the value that the outside world gives it (see docs/PADS.md when it exists). */

#ifndef HAND_IOBUF_H
#define HAND_IOBUF_H

#include "vsim.h"

typedef struct iobuf_t
{
    vs_sig  *i, *io, *o, *t;
} iobuf_t;

void iobuf_create(vs_kernel *k, iobuf_t *self, const char *path, vs_sig *i, vs_sig *io, vs_sig *o, vs_sig *t);

#endif
