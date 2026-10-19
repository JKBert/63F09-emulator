/* ROM_27F512 : 64K x 8 ROM made of block RAMs. The data is read on the rising edge of CLOCK when ROM_ENABLE is
 * set, and held until the next enabled edge ; the output is all ones when the ROM is not selected. MRDY is always
 * 1 (the asynchronous variant of the VHDL is not used). The content comes from the loader. */

#ifndef HAND_ROM_27F512_H
#define HAND_ROM_27F512_H

#include "vsim.h"

typedef struct rom_27f512_t
{
    uint8_t     *mem;
    uint8_t     latch;
    vs_sig      *clock, *enable, *address, *data_output, *mrdy;
} rom_27f512_t;

void rom_27f512_create(vs_kernel *k, rom_27f512_t *self, const char *path, vs_sig *clock, vs_sig *rom_enable,
                       vs_sig *address, vs_sig *data_output, vs_sig *mrdy);

#endif
