#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include "soc/pins.h"

void pins_init(pins *p)
{
    memset(p, 0, sizeof(*p));
    p->listen_fd = p->conn_fd = -1;
}

void pins_add(pins *p, const char *name, vs_sig *sig, unsigned bit, int kind)
{
    pin     *q;
    int     i;

    if (p->npin == PINS_MAX)
    {
        return;
    }
    q = &p->pin[p->npin++];
    snprintf(q->name, sizeof(q->name), "%s", name);
    q->sig = sig;
    q->bit = bit;
    q->kind = kind;
    q->watch = 1;
    q->last = -1;
    for (i = 0; i < p->nsens; i++)
    {
        if (p->sens[i] == sig)
        {
            return;
        }
    }
    p->sens[p->nsens++] = sig;
}

static int level(const pin *q)
{
    return (int) ((q->sig->cur >> q->bit) & 1);
}

static void send_line(pins *p, uint64_t now, const pin *q, int v)
{
    char    line[64];
    int     n;

    if (p->conn_fd < 0)
    {
        return;
    }
    n = snprintf(line, sizeof(line), "%llu %s %d\n", (unsigned long long) (now / 144), q->name, v);
    if (send(p->conn_fd, line, (size_t) n, MSG_NOSIGNAL) < 0 && errno != EAGAIN && errno != EWOULDBLOCK)
    {
        close(p->conn_fd);
        p->conn_fd = -1;
    }
}

static void pins_run(void *inst)
{
    pins    *p = inst;
    int     i;

    for (i = 0; i < p->npin; i++)
    {
        pin *q = &p->pin[i];
        int v = level(q);

        if (v != q->last)
        {
            q->last = v;
            if (q->watch)
            {
                send_line(p, p->k->now, q, v);
            }
        }
    }
}

static void set_watch(pins *p, const char *prefix, int on)
{
    int     i;
    size_t  n = strlen(prefix);

    for (i = 0; i < p->npin; i++)
    {
        if (strncmp(p->pin[i].name, prefix, n) == 0)
        {
            p->pin[i].watch = on;
            if (on)
            {
                send_line(p, p->k->now, &p->pin[i], level(&p->pin[i]));
            }
        }
    }
}

static void command(pins *p, char *line);

typedef struct delayed
{
    pins    *p;
    char    line[48];
} delayed;

static void run_delayed(vs_kernel *k, void *arg)
{
    delayed *d = arg;

    (void) k;
    command(d->p, d->line);
}

static void command(pins *p, char *line)
{
    char                name[32], val[8];
    int                 i;
    unsigned long long  ns;
    int                 skip;

    if (sscanf(line, "at %llu %n", &ns, &skip) == 1 && skip > 0)
    {
        delayed *d = vs_alloc(p->k, sizeof(*d));

        d->p = p;
        snprintf(d->line, sizeof(d->line), "%s", line + skip);
        vs_timer_add(p->k, (uint64_t) ns * 144, run_delayed, d);        /* simulated time, in nanoseconds */
    }
    else if (sscanf(line, "watch %31s", name) == 1)
    {
        set_watch(p, name, 1);
    }
    else if (sscanf(line, "unwatch %31s", name) == 1)
    {
        set_watch(p, name, 0);
    }
    else if (sscanf(line, "%31s %7s", name, val) == 2)
    {
        for (i = 0; i < p->npin; i++)
        {
            pin *q = &p->pin[i];

            if (strcmp(q->name, name) != 0)
            {
                continue;
            }
            if (q->kind == PIN_IN && (val[0] == '0' || val[0] == '1'))
            {
                vs_drive_bits(q->sig, q->bit, 1, (uint64_t) (val[0] - '0'));
            }
            else if (q->kind == PIN_OD)
            {
                vs_pull(q->sig, UINT64_C(1) << q->bit, val[0] == '0');
            }
            return;
        }
    }
}

static void accept_peer(pins *p)
{
    int     fd, i;

    if (p->listen_fd < 0 || p->conn_fd >= 0)
    {
        return;
    }
    fd = accept(p->listen_fd, NULL, NULL);
    if (fd < 0)
    {
        return;
    }
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    p->conn_fd = fd;
    p->len = 0;
    for (i = 0; i < p->npin; i++)
    {
        p->pin[i].watch = 1;
        send_line(p, p->k->now, &p->pin[i], level(&p->pin[i]));
    }
}

static void poll_peer(vs_kernel *k, void *arg)
{
    pins    *p = arg;
    ssize_t n;

    accept_peer(p);
    if (p->conn_fd >= 0)
    {
        n = recv(p->conn_fd, p->buf + p->len, sizeof(p->buf) - 1 - p->len, 0);
        if (n > 0)
        {
            char *nl;

            p->len += (size_t) n;
            p->buf[p->len] = '\0';
            while ((nl = strchr(p->buf, '\n')) != NULL)
            {
                *nl = '\0';
                command(p, p->buf);
                memmove(p->buf, nl + 1, strlen(nl + 1) + 1);
                p->len = strlen(p->buf);
            }
            if (p->len >= sizeof(p->buf) - 1)
            {
                p->len = 0;                     /* a line too long : dropped */
            }
        }
        else if (n == 0 || (errno != EAGAIN && errno != EWOULDBLOCK))
        {
            int i;

            close(p->conn_fd);                  /* the peer left : its pulls are released */
            p->conn_fd = -1;
            for (i = 0; i < p->npin; i++)
            {
                if (p->pin[i].kind == PIN_OD)
                {
                    vs_pull(p->pin[i].sig, UINT64_C(1) << p->pin[i].bit, 0);
                }
            }
        }
    }
    vs_timer_add(k, k->now + PINS_POLL, poll_peer, p);
}

void pins_create(vs_kernel *k, pins *p)
{
    int i;

    p->k = k;
    for (i = 0; p->conn_fd >= 0 && i < p->npin; i++)
    {
        send_line(p, k->now, &p->pin[i], level(&p->pin[i]));
    }
    vs_register_process(k, pins_run, p, p->sens, (size_t) p->nsens);
    vs_timer_add(k, k->now + PINS_POLL, poll_peer, p);
}

int pins_listen(pins *p, const char *path, int wait)
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
    strcpy(p->path, path);
    p->listen_fd = fd;
    if (wait)
    {
        p->conn_fd = accept(fd, NULL, NULL);
        if (p->conn_fd < 0)
        {
            return -1;
        }
        fcntl(p->conn_fd, F_SETFL, fcntl(p->conn_fd, F_GETFL, 0) | O_NONBLOCK);
    }
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
    return 0;
}

void pins_close(pins *p)
{
    if (p->conn_fd >= 0)
    {
        close(p->conn_fd);
    }
    if (p->listen_fd >= 0)
    {
        close(p->listen_fd);
        unlink(p->path);
    }
}
