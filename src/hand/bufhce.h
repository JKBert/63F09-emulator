/* BUFHCE : clock buffer with a clock enable, in its CE_TYPE = "SYNC" flavour : CE is latched while the
 * clock is low, so that the clock never gets cut in the middle of a pulse. */

#ifndef HAND_BUFHCE_H
#define HAND_BUFHCE_H

#include "vsim.h"

typedef struct bufhce_t
{
    vs_sig  *ce, *i, *o;
    vs_sig  latch;
} bufhce_t;

void bufhce_create(vs_kernel *k, bufhce_t *self, const char *path, vs_sig *ce, vs_sig *i, vs_sig *o);

#endif
