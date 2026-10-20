/* Snapshots : the whole state of a run (kernel, instances, models, memories) lives in one arena at a fixed address
 * (src/rt/vsim.c), so a snapshot is the content of that arena and the pointers inside it stay valid when it is loaded
 * again. The executable must be the same one (it is checked by a hash) and linked without PIE (the code addresses are
 * in the timers and the processes). The host side (files, sockets, pins) is not part of the snapshot : it is set again
 * from the command line by soc_rehost(). */

#ifndef SOC_SNAPSHOT_H
#define SOC_SNAPSHOT_H

#include "soc/soc.h"

/* Writes the state ; the kernel must be settled (between two vs_advance). Returns 0 on success. */
int  snapshot_save(soc *s, const char *path);

/* Maps the arena, loads the file in it and returns the soc, or NULL (a message is printed). */
soc *snapshot_load(const char *path);

/* Gives the host side of a loaded soc the files, sockets and pins of the command line `host`. Returns 0 on success. */
int  soc_rehost(soc *s, const soc_cfg *host);

#endif
