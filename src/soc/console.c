#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
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
    if (c->conn_fd >= 0)
    {
        unsigned char b = (unsigned char) c->tx_byte;

        if (send(c->conn_fd, &b, 1, MSG_NOSIGNAL) < 0 && errno != EAGAIN)
        {
            close(c->conn_fd);
            c->conn_fd = -1;
        }
    }
    else if (c->out != NULL)
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

static int accept_peer(console *c)
{
    int fd;

    if (c->listen_fd < 0 || c->conn_fd >= 0)
    {
        return c->conn_fd >= 0;
    }
    fd = accept(c->listen_fd, NULL, NULL);
    if (fd < 0)
    {
        return 0;
    }
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    c->conn_fd = fd;
    return 1;
}

/* One byte from the host, or -1 when there is none yet, -2 when there will be none. */
static int host_byte(console *c)
{
    struct pollfd p;
    int           ch;

    if (c->listen_fd >= 0)
    {
        unsigned char b;
        ssize_t       n;

        if (!accept_peer(c))
        {
            return -1;
        }
        n = recv(c->conn_fd, &b, 1, 0);
        if (n == 1)
        {
            return b;
        }
        if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK))
        {
            close(c->conn_fd);          /* the peer left : wait for the next one */
            c->conn_fd = -1;
        }
        return -1;
    }
    if (c->in == NULL || c->in_done)
    {
        return -2;
    }
    p.fd = fileno(c->in);
    p.events = POLLIN;
    if (c->in_is_tty_or_pipe && poll(&p, 1, 0) <= 0)
    {
        return -1;
    }
    ch = fgetc(c->in);
    if (ch == EOF)
    {
        c->in_done = 1;
        return -2;
    }
    return ch;
}

static void poll_input(vs_kernel *k, void *arg)
{
    console     *c = arg;
    int         ch = host_byte(c);
    frame       *f;

    if (ch == -2)
    {
        return;
    }
    if (ch == -1)
    {
        vs_timer_add(k, k->now + POLL_TICKS, poll_input, c);
        return;
    }
    f = vs_alloc(k, sizeof(*f));
    f->c = c;
    f->bit = 0;
    f->byte = (unsigned) ch;
    send_bit(k, f);
}

void console_init(console *c)
{
    memset(c, 0, sizeof(*c));
    c->listen_fd = -1;
    c->conn_fd = -1;
}

int console_listen(console *c, const char *path, int wait)
{
    struct sockaddr_un a;
    int                fd = socket(AF_UNIX, SOCK_STREAM, 0);

    if (fd < 0 || strlen(path) >= sizeof(a.sun_path))
    {
        return -1;
    }
    memset(&a, 0, sizeof(a));
    a.sun_family = AF_UNIX;
    strcpy(a.sun_path, path);
    unlink(path);
    if (bind(fd, (struct sockaddr *) &a, sizeof(a)) < 0 || listen(fd, 1) < 0)
    {
        perror(path);
        close(fd);
        return -1;
    }
    strcpy(c->sock_path, path);
    if (wait)
    {
        c->listen_fd = fd;
        c->conn_fd = accept(fd, NULL, NULL);
        if (c->conn_fd < 0)
        {
            return -1;
        }
        fcntl(c->conn_fd, F_SETFL, fcntl(c->conn_fd, F_GETFL, 0) | O_NONBLOCK);
    }
    c->listen_fd = fd;
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    return 0;
}

void console_close(console *c)
{
    if (c->conn_fd >= 0)
    {
        close(c->conn_fd);
    }
    if (c->listen_fd >= 0)
    {
        close(c->listen_fd);
        unlink(c->sock_path);
    }
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
    if (in != NULL || c->listen_fd >= 0)
    {
        vs_timer_add(k, POLL_TICKS, poll_input, c);
    }
}
