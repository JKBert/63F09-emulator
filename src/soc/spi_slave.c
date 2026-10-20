#include <string.h>

#include "soc/spi_slave.h"

static void present(spi_slave *s)
{
    vs_pull(s->miso, 1, ((s->tx >> (7 - s->cnt)) & 1) == 0);
}

static void spi_run(void *inst)
{
    spi_slave   *s = inst;
    int         selected = (s->ss->cur & 1) == 0;

    if (vs_falling_bit(s->ss, 0))
    {
        s->cnt = 0;
        s->rx = 0;
        s->tx = s->last;
        present(s);
        return;
    }
    if (!selected)
    {
        vs_pull(s->miso, 1, 0);                 /* released */
        return;
    }
    if (vs_rising(s->sclk))
    {
        s->rx = ((s->rx << 1) | (unsigned) (s->mosi->cur & 1)) & 0xFF;
        s->cnt++;
        if (s->cnt == 8)
        {
            s->last = s->rx;
            s->bytes++;
        }
    }
    else if (vs_falling(s->sclk))
    {
        if (s->cnt == 8)
        {
            s->cnt = 0;                         /* next byte of the same select */
            s->tx = s->last;
            s->rx = 0;
        }
        present(s);
    }
}

void spi_slave_create(vs_kernel *k, spi_slave *s, vs_sig *ss, vs_sig *sclk, vs_sig *mosi, vs_sig *miso)
{
    vs_sig  *sens[2];

    memset(s, 0, sizeof(*s));
    s->ss = ss;
    s->sclk = sclk;
    s->mosi = mosi;
    s->miso = miso;
    s->last = 0xA5;
    miso->wand = 1;
    sens[0] = ss;
    sens[1] = sclk;
    vs_register_process(k, spi_run, s, sens, 2);
}
