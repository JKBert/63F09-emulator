/* Test bench of CLK_63F75 : reads stim.txt (one "reset_n mrdy" pair per tick), drives TICK low
 * then high, and prints E Q C after each settle. */

#include <stdio.h>
#include <stdlib.h>

#include "clk_63f75.h"

int main(int argc, char **argv)
{
    vs_kernel   k;
    vs_sig      reset_n, mrdy, tick, e, q, c;
    clk_63f75   dut;
    FILE        *f;
    int         r, m;

    if (argc != 2)
    {
        fprintf(stderr, "usage: %s stim.txt\n", argv[0]);
        return 2;
    }
    f = fopen(argv[1], "r");
    if (f == NULL)
    {
        perror(argv[1]);
        return 2;
    }

    vs_kernel_init(&k);
    vs_register_signal(&k, &reset_n, 0);
    vs_register_signal(&k, &mrdy, 0);
    vs_register_signal(&k, &tick, 0);
    vs_register_signal(&k, &e, 0);
    vs_register_signal(&k, &q, 0);
    vs_register_signal(&k, &c, 0);
    clk_63f75_create(&k, &dut, &reset_n, &mrdy, &tick, &e, &q, &c);
    vs_settle(&k);

    while (fscanf(f, "%d %d", &r, &m) == 2)
    {
        vs_drive(&reset_n, (uint64_t) r);
        vs_drive(&mrdy, (uint64_t) m);
        vs_drive(&tick, 0);
        vs_settle(&k);
        printf("%d %d %d\n", (int) e.cur, (int) q.cur, (int) c.cur);
        vs_drive(&tick, 1);
        vs_settle(&k);
        printf("%d %d %d\n", (int) e.cur, (int) q.cur, (int) c.cur);
    }
    fclose(f);
    vs_kernel_free(&k);
    return 0;
}
