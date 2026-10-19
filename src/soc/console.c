#include <poll.h>
#include <stdlib.h>
#include <unistd.h>

#include "soc/console.h"
#include "soc/soc.h"

/* ticks per second : EXTAL has a period of 2 * SOC_EXTAL_HALF ticks and runs at 24 MHz */
#define TICKS_PER_SECOND    (UINT64_C(24000000) * 2 * SOC_EXTAL_HALF)

/* Polling of the host input, in ticks (about 20 microseconds of simulated time when no byte is waiting). */
#define POLL_TICKS          (2 * SOC_EXTAL_HALF * 480)

static void sample_bit(vs_kernel *k, void *arg)
{
    console *c = arg;

    if (c->tx_nbits == (unsigned) -1)
    {
        /* the middle of the start bit : a glitch is not a start */
        if (c->txd->cur != 0)
        {
            c->tx_busy = 0;
            return;
        }
        c->tx_nbits = 0;
        vs_timer_add(k, k->now + c->bit_ticks, sample_bit, c);
        return;
    }
    if (c->tx_nbits < 8)
    {
        c->tx_byte |= (unsigned) (c->txd->cur & 1) << c->tx_nbits;
        c->tx_nbits++;
        vs_timer_add(k, k->now + c->bit_ticks, sample_bit, c);
        return;
    }
    /* the stop bit : the byte is complete */
    if (c->out != NULL)
    {
        fputc((int) c->tx_byte, c->out);
        fflush(c->out);
    }
    c->tx_count++;
    c->tx_busy = 0;
}

static void txd_run(void *inst)
{
    console *c = inst;

    if (getenv("CONSOLE_DEBUG") && c->txd->evt)
    {
        fprintf(stderr, "txd=%d at %llu\n", (int) c->txd->cur, (unsigned long long) c->k->now);
    }
    if (!c->tx_busy && vs_falling(c->txd))
    {
        c->tx_busy = 1;
        c->tx_nbits = (unsigned) -1;
        c->tx_byte = 0;
        vs_timer_add(c->k, c->k->now + c->bit_ticks / 2, sample_bit, c);
    }
}

typedef struct frame
{
    console     *c;
    unsigned    bit;                /* 0 : start, 1..8 : data, 9 : stop */
    unsigned    byte;
} frame;

static void poll_input(vs_kernel *k, void *arg);

static void send_bit(vs_kernel *k, void *arg)
{
    frame   *f = arg;
    console *c = f->c;

    if (f->bit == 0)
    {
        vs_drive(c->rxd, 0);
    }
    else if (f->bit <= 8)
    {
        vs_drive(c->rxd, (f->byte >> (f->bit - 1)) & 1);
    }
    else
    {
        vs_drive(c->rxd, 1);
    }
    f->bit++;
    if (f->bit <= 9)
    {
        vs_timer_add(k, k->now + c->bit_ticks, send_bit, f);
    }
    else
    {
        c->rx_count++;
        vs_timer_add(k, k->now + c->bit_ticks, poll_input, c);      /* the stop bit lasts a bit */
    }
}

static void poll_input(vs_kernel *k, void *arg)
{
    console     *c = arg;
    int         ch;
    frame       *f;
    struct pollfd p;

    if (c->in == NULL || c->in_done)
    {
        return;
    }
    p.fd = fileno(c->in);
    p.events = POLLIN;
    if (c->in_is_tty_or_pipe && poll(&p, 1, 0) <= 0)
    {
        vs_timer_add(k, k->now + POLL_TICKS, poll_input, c);
        return;
    }
    ch = fgetc(c->in);
    if (ch == EOF)
    {
        c->in_done = 1;
        return;
    }
    f = vs_alloc(k, sizeof(*f));
    f->c = c;
    f->bit = 0;
    f->byte = (unsigned) ch;
    send_bit(k, f);
}

void console_create(vs_kernel *k, console *c, vs_sig *rxd, vs_sig *txd, unsigned baud, FILE *in, FILE *out)
{
    vs_sig  *sens[1];

    c->k = k;
    c->rxd = rxd;
    c->txd = txd;
    c->bit_ticks = TICKS_PER_SECOND / baud;
    c->in = in;
    c->out = out;
    c->in_is_tty_or_pipe = in != NULL && (in == stdin);
    c->tx_busy = c->rx_busy = c->in_done = 0;
    c->tx_count = c->rx_count = 0;
    sens[0] = txd;
    vs_register_process(k, txd_run, c, sens, 1);
    if (in != NULL)
    {
        vs_timer_add(k, POLL_TICKS, poll_input, c);
    }
}
