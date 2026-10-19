/* Behaviour of the block RAMs of the SoC (RAMB18E1 as the 61F64x1 and 61F512 use them) : a memory with two
 * independent synchronous ports, READ_FIRST, no output register. A port that is not enabled keeps its output.
 * Each of the four 16K blocks of a 64K bank has its own output latch ; the data out is that of the block that
 * the address selects now. */

#ifndef HAND_RAMCORE_H
#define HAND_RAMCORE_H

#include "vsim.h"

typedef struct ramcore_t
{
    unsigned    bits;               /* 1 or 8 */
    uint8_t     *mem;               /* 65536 words */
    uint8_t     out[2][4];          /* output latch of each block of each port */
    vs_sig      *clk[2], *rw[2], *addr[2], *din[2], *dout[2], *en[2];
} ramcore_t;

/* en[p] may be NULL (port always enabled). */
void ramcore_create(vs_kernel *k, ramcore_t *self, unsigned bits, vs_sig *clk, vs_sig *rw, vs_sig *addr, vs_sig *din,
                    vs_sig *dout, vs_sig *en, vs_sig *clk2, vs_sig *rw2, vs_sig *addr2, vs_sig *din2, vs_sig *dout2,
                    vs_sig *en2);

/* The content of the memory, for the loader (ELF) and the debugger. */
uint8_t *ramcore_data(ramcore_t *self);

#endif
