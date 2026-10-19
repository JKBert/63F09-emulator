/* PLLE2_BASE : clock synthesiser. Its outputs are timed square waves derived from CLKIN1 :
 *   period(CLKOUTn) = period(CLKIN1) * DIVCLK_DIVIDE * CLKOUTn_DIVIDE / CLKFBOUT_MULT
 * The first edge of each output is the first rising edge of CLKIN1 and LOCKED rises after PLL_LOCK_CYCLES CLKIN1
 * periods. The period of CLKIN1 is measured between its two first rising edges. */

#ifndef HAND_PLLE2_BASE_H
#define HAND_PLLE2_BASE_H

#include "vsim.h"

#define PLL_LOCK_CYCLES 8

typedef struct plle2_base_t
{
    vs_sig      *clkfbin, *clkin1, *pwrdwn, *rst, *clkfbout, *clkout0, *clkout1, *locked;
    int64_t     mult, divclk, div0, div1;
    uint64_t    first, period;
    unsigned    cycles;
    int         running;
} plle2_base_t;

void plle2_base_create(vs_kernel *k, plle2_base_t *self, const char *path, int64_t clkfbout_mult, int64_t clkout0_divide,
                       int64_t clkout1_divide, int64_t divclk_divide, vs_sig *clkfbin, vs_sig *clkin1,
                       vs_sig *pwrdwn, vs_sig *rst, vs_sig *clkfbout, vs_sig *clkout0, vs_sig *clkout1, vs_sig *locked);

#endif
