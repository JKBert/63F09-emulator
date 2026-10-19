/* RAM_61F32x64 : one RAMB36E1 as a 512 x 64 simple dual-port memory. The read data is available one RDCLK edge
 * after the address ; a read of the address that is written at the same time returns the old value. */

#ifndef HAND_RAM_61F32X64_H
#define HAND_RAM_61F32X64_H

#include "vsim.h"

typedef struct ram_61f32x64_t
{
    uint64_t    *mem;
    uint64_t    out;
    vs_sig      *rdclk, *wrclk, *we, *rdaddr, *wraddr, *din, *dout;
} ram_61f32x64_t;

void ram_61f32x64_create(vs_kernel *k, ram_61f32x64_t *self, const char *path, vs_sig *rdclk, vs_sig *wrclk,
                         vs_sig *we, vs_sig *rdaddr, vs_sig *wraddr, vs_sig *data_in, vs_sig *data_out);

#endif
