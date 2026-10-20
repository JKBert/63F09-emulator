#include <string.h>

#include "soc/i2c_eeprom.h"

enum { IDLE, ADDRESS, WORD, WDATA, RDATA };

static void release(i2c_eeprom *e)
{
    vs_pull(e->sda, 1, 0);
}

static void pull_low(i2c_eeprom *e)
{
    vs_pull(e->sda, 1, 1);
}

/* the bit of the byte being sent that is due at this falling edge */
static void drive_bit(i2c_eeprom *e, unsigned k)
{
    if ((e->tx >> (7 - k)) & 1)
    {
        release(e);
    }
    else
    {
        pull_low(e);
    }
}

static void eeprom_run(void *inst)
{
    i2c_eeprom  *e = inst;
    int         scl = (int) (e->scl->cur & 1);

    /* START and STOP : a change of SDA while SCL is high (the model itself changes SDA only while SCL is low) */
    if (scl && vs_falling(e->sda))
    {
        e->phase = ADDRESS;
        e->cnt = 0;
        e->shift = 0;
        e->starts++;
        release(e);
        return;
    }
    if (scl && vs_rising(e->sda))
    {
        e->phase = IDLE;
        e->stops++;
        release(e);
        return;
    }
    if (e->phase == IDLE)
    {
        return;
    }
    if (vs_rising(e->scl))
    {
        if (e->cnt < 8 && e->phase != RDATA)
        {
            e->shift = ((e->shift << 1) | (unsigned) (e->sda->cur & 1)) & 0xFF;
        }
        else if (e->cnt == 8 && e->phase == RDATA)
        {
            e->master_ack = (e->sda->cur & 1) == 0;
        }
        e->cnt++;
    }
    else if (vs_falling(e->scl))
    {
        if (e->phase != RDATA && e->cnt == 8)
        {
            /* a byte is complete : acknowledge it */
            int ack = 0;

            switch (e->phase)
            {
                case ADDRESS:
                    if ((e->shift >> 1) == e->addr7)
                    {
                        ack = 1;
                        e->next_phase = (e->shift & 1) ? RDATA : WORD;
                    }
                    break;
                case WORD:
                    e->ptr = e->shift;
                    ack = 1;
                    e->next_phase = WDATA;
                    break;
                default:                /* WDATA */
                    e->mem[e->ptr] = (uint8_t) e->shift;
                    e->ptr = (e->ptr + 1) & 0xFF;
                    e->writes++;
                    ack = 1;
                    e->next_phase = WDATA;
                    break;
            }
            if (ack)
            {
                pull_low(e);
            }
            else
            {
                e->phase = IDLE;        /* not for us : stay out until the next START */
            }
        }
        else if (e->phase != RDATA && e->cnt == 9)
        {
            release(e);
            e->cnt = 0;
            e->shift = 0;
            e->phase = e->next_phase;
            if (e->phase == RDATA)
            {
                e->tx = e->mem[e->ptr];
                e->reads++;
                drive_bit(e, 0);
            }
        }
        else if (e->phase == RDATA)
        {
            if (e->cnt >= 1 && e->cnt <= 7)
            {
                drive_bit(e, e->cnt);
            }
            else if (e->cnt == 8)
            {
                release(e);             /* the master acknowledges */
            }
            else if (e->cnt == 9)
            {
                e->cnt = 0;
                if (e->master_ack)
                {
                    e->ptr = (e->ptr + 1) & 0xFF;
                    e->tx = e->mem[e->ptr];
                    e->reads++;
                    drive_bit(e, 0);
                }
                else
                {
                    e->phase = IDLE;
                    release(e);
                }
            }
        }
    }
}

void i2c_eeprom_create(vs_kernel *k, i2c_eeprom *e, vs_sig *sda, vs_sig *scl, unsigned addr7)
{
    vs_sig  *sens[2];

    memset(e, 0, sizeof(*e));
    memset(e->mem, 0xFF, sizeof(e->mem));
    e->sda = sda;
    e->scl = scl;
    e->addr7 = addr7;
    sda->wand = 1;
    scl->wand = 1;
    sens[0] = sda;
    sens[1] = scl;
    vs_register_process(k, eeprom_run, e, sens, 2);
}
