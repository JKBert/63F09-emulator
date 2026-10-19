/* RAM_61F512 : 64K x 8 dual-port RAM (USE_RAMBLOCKS = true : eight 61F64x1 in parallel). */

#ifndef HAND_RAM_61F512_H
#define HAND_RAM_61F512_H

#include "hand/ramcore.h"

typedef struct ram_61f512_t
{
    ramcore_t   core;
} ram_61f512_t;

void ram_61f512_create(vs_kernel *k, ram_61f512_t *self, const char *path, vs_sig *memclk, vs_sig *rw,
                       vs_sig *address, vs_sig *data_in, vs_sig *data_out, vs_sig *memclk2, vs_sig *rw2,
                       vs_sig *address2, vs_sig *data_in2, vs_sig *data_out2, vs_sig *valid_addr,
                       vs_sig *valid_addr2);

#endif
