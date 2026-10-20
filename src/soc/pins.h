/* The pins of the peripherals on a Unix domain socket. A peer (a script, a GUI, a simulated board) sees the level
 * of every pin and drives the inputs, as text lines :
 *
 *   emulator to peer   "<ns> <pin> <0|1>\n"     the pin changed (and, at connection, its current level)
 *   peer to emulator   "<pin> <0|1|z>\n"        drive an input pin ; for an open-drain pad 0 pulls it low and 1 or z releases it
 *                      "watch <prefix>\n"       only the pins whose name starts with the prefix are reported (default : all)
 *                      "unwatch <prefix>\n"     the opposite
 *
 * Pin names : pia<0-4>.pa<0-7> (open drain), pia<n>.c1 (input), pia<n>.c2 (open drain), ptm<0-1>.o<1-3> (output),
 * ptm<n>.c<1-3>, ptm<n>.g<1-3> (inputs, as the VHDL ports C_n and G_n : active low), spi.sclk, spi.mosi, spi.miso,
 * spi.ss<0-15> (open drain), twi.sda, twi.scl (open drain), irq, firq, nmi (inputs, active low), eirq<0-7> (inputs,
 * active low). The time is the simulated one, in nanoseconds. */

#ifndef SOC_PINS_H
#define SOC_PINS_H

#include "vsim.h"

enum pin_kind
{
    PIN_OUT,            /* driven by the design : observed only */
    PIN_IN,             /* driven by the peer */
    PIN_OD              /* open drain : the peer can pull it low */
};

#define PINS_MAX    256
#define PINS_POLL   144000      /* the peer is polled every microsecond of simulated time (ticks) */

typedef struct pin
{
    char        name[16];
    vs_sig      *sig;
    unsigned    bit;
    int         kind;
    int         watch;
    int         last;
} pin;

typedef struct pins
{
    vs_kernel   *k;
    pin         pin[PINS_MAX];
    int         npin;
    vs_sig      *sens[PINS_MAX];
    int         nsens;
    int         listen_fd, conn_fd;
    char        path[108];
    char        buf[256];
    size_t      len;
} pins;

void pins_init(pins *p);
void pins_add(pins *p, const char *name, vs_sig *sig, unsigned bit, int kind);
/* Listens on `path` ; with `wait` blocks until a peer connects. Returns 0 on success. */
int  pins_listen(pins *p, const char *path, int wait);
/* Starts watching the pins and polling the peer (after all pins_add). */
void pins_create(vs_kernel *k, pins *p);
void pins_close(pins *p);

#endif
