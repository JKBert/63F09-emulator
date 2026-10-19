#include "hand/ram_61f64x1.h"

void ram_61f64x1_create(vs_kernel *k, ram_61f64x1_t *self, const char *path, vs_sig *memclk, vs_sig *memclk2,
                        vs_sig *rw, vs_sig *rw2, vs_sig *address, vs_sig *address2, vs_sig *valid_addr,
                        vs_sig *valid_addr2, vs_sig *data_in, vs_sig *data_out, vs_sig *data_in2, vs_sig *data_out2)
{
    (void) path;
    ramcore_create(k, &self->core, 1, memclk, rw, address, data_in, data_out, valid_addr,
                   memclk2, rw2, address2, data_in2, data_out2, valid_addr2);
}
