/* Host side of a serial line : the bytes that the emulated UART sends are written to a file (stdout), the bytes
 * read from a file (stdin) are sent to it as 8N1 frames. The line has a fixed rate : it must be the one that the
 * program configures in the ACIA (the ACIA divides SYSCLK, 24 MHz). */

#ifndef SOC_CONSOLE_H
#define SOC_CONSOLE_H

#include <stdio.h>

#include "vsim.h"

typedef struct console
{
    vs_kernel   *k;
    vs_sig      *rxd;               /* driven by the host */
    vs_sig      *txd;               /* driven by the ACIA */
    uint64_t    bit_ticks;
    FILE        *in, *out;
    int         listen_fd;          /* Unix socket the host side listens on (-1 : none) */
    int         conn_fd;            /* the connected peer (-1 : none) : bytes go there instead of `out` */
    int         in_is_tty_or_pipe;  /* poll before reading */
    /* transmit side (ACIA to host) */
    int         tx_busy;
    unsigned    tx_nbits;
    unsigned    tx_byte;
    /* receive side (host to ACIA) */
    int         rx_busy;
    int         in_done;
    uint64_t    tx_count, rx_count;
    char        sock_path[108];
} console;

/* Call console_init, then (optionally) console_listen, then console_create.
 * `baud` in bits per second. `in` and `out` may be NULL. The console watches `txd` and drives `rxd`. */
void console_init(console *c);
void console_create(vs_kernel *k, console *c, vs_sig *rxd, vs_sig *txd, unsigned baud, FILE *in, FILE *out);

/* The serial line goes to a Unix domain socket (stream) : the emulator listens on `path` and serves one peer at a
 * time, bytes are exchanged raw. With `wait` the call blocks until a peer connects. Returns 0 on success. */
int  console_listen(console *c, const char *path, int wait);

/* Closes the descriptors and removes the socket file. */
void console_close(console *c);

#endif
