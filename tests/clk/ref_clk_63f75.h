#ifndef REF_CLK_63F75_H
#define REF_CLK_63F75_H

#include "vsim.h"

/* Reference translation of entity CLK_63F75, written by hand : the generator must produce
 * the same structure (ports as pointers to the parent's signals, internal signals embedded). */
typedef struct clk_63f75
{
    vs_sig  *reset_n, *mrdy, *tick;
    vs_sig  *e, *q, *c;
    vs_sig  position;
} clk_63f75;

void clk_63f75_create(vs_kernel *k, clk_63f75 *self,
                      vs_sig *reset_n, vs_sig *mrdy, vs_sig *tick,
                      vs_sig *e, vs_sig *q, vs_sig *c);

#endif
