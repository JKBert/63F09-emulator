/* The I2C EEPROM model alone : a master written here drives SDA and SCL. Checks the page of write and the write cycle. */

#include <stdio.h>
#include <stdlib.h>

#include "soc/i2c_eeprom.h"

static vs_kernel   k;
static vs_sig      sda, scl;
static i2c_eeprom  ee;

static void lines(int c, int d)
{
    if (c)                              /* SCL goes high after SDA is set, and goes low before it changes : never a START or a STOP by chance */
    {
        vs_drive(&sda, (uint64_t) d);
        vs_settle(&k);
        vs_drive(&scl, 1);
    }
    else
    {
        vs_drive(&scl, 0);
        vs_settle(&k);
        vs_drive(&sda, (uint64_t) d);
    }
    vs_settle(&k);
}

static void start(void)
{
    lines(0, 1);
    lines(1, 1);
    lines(1, 0);
}

static void stop(void)
{
    lines(0, 0);
    lines(1, 0);
    lines(1, 1);
}

/* sends a byte ; returns the acknowledge (1 : acknowledged) */
static int send(unsigned v)
{
    int i, ack;

    for (i = 7; i >= 0; i--)
    {
        lines(0, (v >> i) & 1);
        lines(1, (v >> i) & 1);
    }
    lines(0, 1);                        /* the master lets SDA go */
    lines(1, 1);
    ack = (sda.cur & 1) == 0;           /* the EEPROM pulls it low */
    lines(0, 1);
    return ack;
}

static int check(const char *what, int ok)
{
    printf("%s: %s\n", what, ok ? "ok" : "FAILED");
    return ok ? 0 : 1;
}

static void init(unsigned page, uint64_t write_ticks)
{
    vs_kernel_init(&k);
    vs_register_signal(&k, &sda, 1);
    vs_register_signal(&k, &scl, 1);
    sda.wand = scl.wand = 1;
    i2c_eeprom_create(&k, &ee, &sda, &scl, 0x50);
    i2c_eeprom_options(&ee, page, write_ticks, NULL);
    vs_settle(&k);
}

static void write_ten(void)
{
    unsigned i;

    start();
    send(0xA0);
    send(0x00);
    for (i = 2; i < 12; i++)
    {
        send(i);                        /* the values 2 to 11 at the addresses 0 to 9 */
    }
    stop();
}

int main(void)
{
    int bad = 0;

    init(8, 0);
    write_ten();
    bad += check("page of 8 : address 8 untouched", ee.mem[8] == 0xFF);
    bad += check("page of 8 : address 0 holds the 9th byte (wrapped)", ee.mem[0] == 10);
    bad += check("page of 8 : address 7 holds the 8th byte", ee.mem[7] == 9);
    init(0, 0);
    write_ten();
    bad += check("no page : address 8 holds the 9th byte", ee.mem[8] == 10);
    bad += check("no page : address 9 holds the 10th byte", ee.mem[9] == 11);
    init(0, 1000);
    start();
    send(0xA0);
    send(0x10);
    send(0x5A);
    stop();
    start();
    bad += check("write cycle : no acknowledge while it lasts", send(0xA0) == 0);
    stop();
    k.now += 2000;
    start();
    bad += check("write cycle : acknowledge after it", send(0xA0) == 1);
    stop();
    return bad;
}
