#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "soc/snapshot.h"

#define SNAP_MAGIC      "63F09SNP"
#define SNAP_VERSION    2
#define PAGE            4096

typedef struct snap_hdr
{
    char        magic[8];
    uint64_t    version;
    uint64_t    exe_hash;       /* FNV-1a of the executable */
    uint64_t    code_addr;      /* address of a function : the executable must be loaded at the same place */
    uint64_t    arena_used;
    uint64_t    soc_addr;
    uint64_t    soc_size;
    uint64_t    parts[VS_MAX_PARTS];    /* the partitions of the kernel */
    uint64_t    gen;
    uint64_t    finished;
    uint64_t    now;
} snap_hdr;

static uint64_t exe_hash(void)
{
    FILE        *f = fopen("/proc/self/exe", "rb");
    uint64_t    h = UINT64_C(1469598103934665603);
    unsigned char buf[65536];
    size_t      n, i;

    if (f == NULL)
    {
        return 0;
    }
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0)
    {
        for (i = 0; i < n; i++)
        {
            h = (h ^ buf[i]) * UINT64_C(1099511628211);
        }
    }
    fclose(f);
    return h;
}

static int zero_page(const uint8_t *p)
{
    const uint64_t  *q = (const uint64_t *) p;
    size_t          i;

    for (i = 0; i < PAGE / 8; i++)
    {
        if (q[i] != 0)
        {
            return 0;
        }
    }
    return 1;
}

int snapshot_save(soc *s, const char *path)
{
    FILE        *f = fopen(path, "wb");
    snap_hdr    h;
    uint8_t     *base;
    size_t      used, pages, i;

    if (f == NULL)
    {
        perror(path);
        return -1;
    }
    vs_arena_region((void **) &base, &used);
    pages = (used + PAGE - 1) / PAGE;
    memset(&h, 0, sizeof(h));
    memcpy(h.magic, SNAP_MAGIC, 8);
    h.version = SNAP_VERSION;
    h.exe_hash = exe_hash();
    h.code_addr = (uint64_t) (uintptr_t) &snapshot_save;
    h.arena_used = used;
    h.soc_addr = (uint64_t) (uintptr_t) s;
    h.soc_size = sizeof(*s);
    for (i = 0; i < VS_MAX_PARTS; i++)
    {
        h.parts[i] = (uint64_t) (uintptr_t) vs_parts[i];
    }
    h.gen = vs_gen;
    h.finished = (uint64_t) vs_finished;
    h.now = s->k.now;
    fwrite(&h, sizeof(h), 1, f);
    /* runs : 0 + count of zero pages, or 1 + one page of data */
    for (i = 0; i < pages;)
    {
        uint8_t     tag;

        if (zero_page(base + i * PAGE))
        {
            uint32_t    n = 0;

            while (i < pages && zero_page(base + i * PAGE))
            {
                n++;
                i++;
            }
            tag = 0;
            fwrite(&tag, 1, 1, f);
            fwrite(&n, sizeof(n), 1, f);
        }
        else
        {
            tag = 1;
            fwrite(&tag, 1, 1, f);
            fwrite(base + i * PAGE, PAGE, 1, f);
            i++;
        }
    }
    if (fclose(f) != 0)
    {
        perror(path);
        return -1;
    }
    return 0;
}

soc *snapshot_load(const char *path)
{
    FILE        *f = fopen(path, "rb");
    snap_hdr    h;
    uint8_t     *base;
    size_t      used, pages, i;

    if (f == NULL)
    {
        perror(path);
        return NULL;
    }
    if (fread(&h, sizeof(h), 1, f) != 1 || memcmp(h.magic, SNAP_MAGIC, 8) != 0 || h.version != SNAP_VERSION)
    {
        fprintf(stderr, "%s: not a snapshot of this version\n", path);
        fclose(f);
        return NULL;
    }
    if (h.code_addr != (uint64_t) (uintptr_t) &snapshot_save || h.exe_hash != exe_hash())
    {
        fprintf(stderr, "%s: made by another executable (or at another address) : load it with the program that saved it\n", path);
        fclose(f);
        return NULL;
    }
    if (h.soc_size != sizeof(soc) || vs_arena_map() != 0)
    {
        fclose(f);
        return NULL;
    }
    vs_arena_region((void **) &base, &used);
    memset(base, 0, used);                  /* what was allocated so far : zero again */
    pages = (h.arena_used + PAGE - 1) / PAGE;
    for (i = 0; i < pages;)
    {
        uint8_t tag;

        if (fread(&tag, 1, 1, f) != 1)
        {
            fprintf(stderr, "%s: truncated\n", path);
            fclose(f);
            return NULL;
        }
        if (tag == 0)
        {
            uint32_t    n;

            if (fread(&n, sizeof(n), 1, f) != 1)
            {
                fclose(f);
                return NULL;
            }
            i += n;
        }
        else
        {
            if (fread(base + i * PAGE, PAGE, 1, f) != 1)
            {
                fprintf(stderr, "%s: truncated\n", path);
                fclose(f);
                return NULL;
            }
            i++;
        }
    }
    fclose(f);
    vs_arena_set_used(h.arena_used);
    for (i = 0; i < VS_MAX_PARTS; i++)
    {
        vs_parts[i] = (vs_part *) (uintptr_t) h.parts[i];
    }
    vs_gen = (uint32_t) h.gen;
    vs_finished = (int) h.finished;
    vs_parts_reset(&((soc *) (uintptr_t) h.soc_addr)->k);
    return (soc *) (uintptr_t) h.soc_addr;
}

int soc_rehost(soc *s, const soc_cfg *host)
{
    int i;

    s->cfg.dump = host->dump;
    s->cfg.trace_bus = host->trace_bus;
    s->cfg.max_ticks = host->max_ticks;
    if (s->cfg.twi_eeprom)
    {
        memcpy(s->cfg.twi_eeprom_file, host->twi_eeprom_file, sizeof(s->cfg.twi_eeprom_file));
        memcpy(s->eeprom.path, host->twi_eeprom_file, sizeof(s->eeprom.path));      /* (not read : the snapshot has the memory) */
    }
    memcpy(s->cfg.save_path, host->save_path, sizeof(s->cfg.save_path));
    s->cfg.save_at = host->save_at;
    for (i = 0; i < SOC_NACIA; i++)
    {
        if (!s->cfg.serial[i].enabled)
        {
            if (host->serial[i].enabled)
            {
                fprintf(stderr, "ACIA %d was not enabled when the snapshot was made\n", i);
                return -1;
            }
            continue;
        }
        s->cfg.serial[i].in = host->serial[i].in;
        s->cfg.serial[i].out = host->serial[i].out;
        memcpy(s->cfg.serial[i].socket, host->serial[i].socket, sizeof(s->cfg.serial[i].socket));
        s->cfg.serial[i].wait = host->serial[i].wait;
        if (console_rehost(&s->con[i], host->serial[i].in, host->serial[i].out, host->serial[i].socket,
                           host->serial[i].wait) != 0)
        {
            return -1;
        }
    }
    s->pins.listen_fd = s->pins.conn_fd = -1;
    if (host->pins_socket[0] != '\0')
    {
        if (s->cfg.pins_socket[0] == '\0')
        {
            fprintf(stderr, "the pins were not enabled when the snapshot was made\n");
            return -1;
        }
        memcpy(s->cfg.pins_socket, host->pins_socket, sizeof(s->cfg.pins_socket));
        s->cfg.pins_wait = host->pins_wait;
        if (pins_listen(&s->pins, s->cfg.pins_socket, s->cfg.pins_wait) != 0)
        {
            return -1;
        }
    }
    return 0;
}
