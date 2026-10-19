#include <stdio.h>
#include <string.h>

#include "acia_63f50.h"

static uint64_t bits(const char *s, size_t w)
{
    uint64_t v = 0;
    size_t i;

    for (i = 0; i < w; i++)
    {
        v = (v << 1) | (s[i] == '1' || s[i] == 'H');
    }
    return v;
}

static vs_w wbits(const char *s, size_t w)
{
    vs_w v = vs_w_zero();
    size_t i;

    for (i = 0; i < w; i++)
    {
        v = vs_w_shl(v, 1, 64 * VS_WIDE_WORDS);
        v.w[0] |= (s[i] == '1' || s[i] == 'H');
    }
    return v;
}

static void put(const vs_sig *s, size_t w)
{
    size_t i;

    for (i = 0; i < w; i++)
    {
        putchar(((s->cur >> (w - 1 - i)) & 1) ? '1' : '0');
    }
    putchar(' ');
}

static void putw(const vs_sig *s, size_t w)
{
    size_t i;

    for (i = 0; i < w; i++)
    {
        size_t b = w - 1 - i;
        putchar(((s[b / 64].cur >> (b % 64)) & 1) ? '1' : '0');
    }
    putchar(' ');
}

int main(int argc, char **argv)
{
    vs_kernel k;
    acia_63f50 dut;
    char line[65536];
    FILE *f, *trace = NULL;
    long phase = 0;

    vs_sig p_e;
    vs_sig p_sysclk;
    vs_sig p_rst_n;
    vs_sig p_cs;
    vs_sig p_mrdy;
    vs_sig p_addr;
    vs_sig p_rw_n;
    vs_sig p_d_in;
    vs_sig p_d_out;
    vs_sig p_irq_n;
    vs_sig p_rxd;
    vs_sig p_txd;
    vs_sig p_dcd_n;
    vs_sig p_cts_n;
    vs_sig p_rts_n;

    if (argc < 2 || (f = fopen(argv[1], "r")) == NULL)
    {
        return 2;
    }
    if (argc > 2)
    {
        trace = fopen(argv[2], "w");
    }
    vs_kernel_init(&k);
    vs_register_signal(&k, &p_e, 0);
    vs_name(&k, &p_e, NULL, "e", 1);
    vs_register_signal(&k, &p_sysclk, 0);
    vs_name(&k, &p_sysclk, NULL, "sysclk", 1);
    vs_register_signal(&k, &p_rst_n, 0);
    vs_name(&k, &p_rst_n, NULL, "rst_n", 1);
    vs_register_signal(&k, &p_cs, 0);
    vs_name(&k, &p_cs, NULL, "cs", 1);
    vs_register_signal(&k, &p_mrdy, 0);
    vs_name(&k, &p_mrdy, NULL, "mrdy", 1);
    vs_register_signal(&k, &p_addr, 0);
    vs_name(&k, &p_addr, NULL, "addr", 2);
    vs_register_signal(&k, &p_rw_n, 0);
    vs_name(&k, &p_rw_n, NULL, "rw_n", 1);
    vs_register_signal(&k, &p_d_in, 0);
    vs_name(&k, &p_d_in, NULL, "d_in", 8);
    vs_register_signal(&k, &p_d_out, 0);
    vs_name(&k, &p_d_out, NULL, "d_out", 8);
    vs_register_signal(&k, &p_irq_n, 0);
    vs_name(&k, &p_irq_n, NULL, "irq_n", 1);
    vs_register_signal(&k, &p_rxd, 0);
    vs_name(&k, &p_rxd, NULL, "rxd", 1);
    vs_register_signal(&k, &p_txd, 0);
    vs_name(&k, &p_txd, NULL, "txd", 1);
    vs_register_signal(&k, &p_dcd_n, 0);
    vs_name(&k, &p_dcd_n, NULL, "dcd_n", 1);
    vs_register_signal(&k, &p_cts_n, 0);
    vs_name(&k, &p_cts_n, NULL, "cts_n", 1);
    vs_register_signal(&k, &p_rts_n, 0);
    vs_name(&k, &p_rts_n, NULL, "rts_n", 1);
    acia_63f50_create(&k, &dut, "dut", &p_e, &p_sysclk, &p_rst_n, &p_cs, &p_mrdy, &p_addr, &p_rw_n, &p_d_in, &p_d_out, &p_irq_n, &p_rxd, &p_txd, &p_dcd_n, &p_cts_n, &p_rts_n);
    vs_settle(&k);
    while (fgets(line, sizeof(line), f) != NULL)
    {
        char *tok;
        tok = strtok(line, " \n");
        vs_drive(&p_rst_n, bits(tok, 1));
        tok = strtok(NULL, " \n");
        vs_drive(&p_cs, bits(tok, 1));
        tok = strtok(NULL, " \n");
        vs_drive(&p_addr, bits(tok, 2));
        tok = strtok(NULL, " \n");
        vs_drive(&p_rw_n, bits(tok, 1));
        tok = strtok(NULL, " \n");
        vs_drive(&p_d_in, bits(tok, 8));
        tok = strtok(NULL, " \n");
        vs_drive(&p_rxd, bits(tok, 1));
        tok = strtok(NULL, " \n");
        vs_drive(&p_dcd_n, bits(tok, 1));
        tok = strtok(NULL, " \n");
        vs_drive(&p_cts_n, bits(tok, 1));
        vs_drive(&p_e, 0);
        vs_drive(&p_sysclk, 0);
        vs_settle(&k);
        if (vs_finished)
        {
            break;     /* the VHDL stopped the simulation (finish) */
        }
        put(&p_mrdy, 1);
        put(&p_d_out, 8);
        put(&p_irq_n, 1);
        put(&p_txd, 1);
        put(&p_rts_n, 1);
        putchar('\n');
        if (trace != NULL)
        {
            vs_dump(&k, trace, phase);
        }
        phase++;
        vs_drive(&p_e, 1);
        vs_drive(&p_sysclk, 1);
        vs_settle(&k);
        if (vs_finished)
        {
            break;     /* the VHDL stopped the simulation (finish) */
        }
        put(&p_mrdy, 1);
        put(&p_d_out, 8);
        put(&p_irq_n, 1);
        put(&p_txd, 1);
        put(&p_rts_n, 1);
        putchar('\n');
        if (trace != NULL)
        {
            vs_dump(&k, trace, phase);
        }
        phase++;
    }
    if (trace != NULL)
    {
        fclose(trace);
    }
    fclose(f);
    vs_kernel_free(&k);
    return 0;
}
