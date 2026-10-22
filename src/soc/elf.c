/* Loader of ELF executables : the segments go to the memory zones, whatever their protection. */

#include <errno.h>
#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"

static uint64_t get(const uint8_t *p, unsigned n, int big)
{
    uint64_t    v = 0;
    unsigned    i;

    for (i = 0; i < n; i++)
    {
        v = big ? (v << 8) | p[i] : v | ((uint64_t) p[i] << (8 * i));
    }
    return v;
}

/* The byte of physical address `addr`, or NULL. */
static uint8_t *byte_at(soc *s, uint64_t addr)
{
    int i;

    if (addr >= SOC_ROM_BASE && addr < SOC_ROM_BASE + 65536)
    {
        vs_region *r = vs_region_find(&s->k, "eprom0");

        return r != NULL ? r->data + (addr - SOC_ROM_BASE) : NULL;
    }
    if (addr >= SOC_INTRAM_BASE && addr < SOC_INTRAM_BASE + 65536)
    {
        vs_region *r = vs_region_find(&s->k, "intram0");

        return r != NULL ? r->data + (addr - SOC_INTRAM_BASE) : NULL;
    }
    for (i = 0; i < s->cfg.nzones; i++)
    {
        soc_zone    *z = &s->cfg.zones[i];

        if (addr >= z->base && addr - z->base < z->size)
        {
            return z->data + (addr - z->base);
        }
    }
    return NULL;
}

uint8_t *soc_byte(soc *s, uint64_t addr)
{
    return byte_at(s, addr);
}

int soc_load_elf(soc *s, const char *path, uint64_t elf_offset)
{
    FILE        *f = fopen(path, "rb");
    uint8_t     id[16], *buf;
    long        len;
    int         is64, big, rc = 0;
    uint64_t    phoff, phentsize, phnum, i;

    if (f == NULL)
    {
        fprintf(stderr, "%s: %s\n", path, strerror(errno));
        return -1;
    }
    fseek(f, 0, SEEK_END);
    len = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = len > 0 ? malloc((size_t) len) : NULL;
    if (buf == NULL || fread(buf, 1, (size_t) len, f) != (size_t) len)
    {
        fprintf(stderr, "%s: cannot read\n", path);
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);
    memcpy(id, buf, len < 16 ? (size_t) len : 16);
    if (len < 52 || memcmp(id, "\177ELF", 4) != 0 || (id[4] != 1 && id[4] != 2) || (id[5] != 1 && id[5] != 2))
    {
        fprintf(stderr, "%s: not an ELF file\n", path);
        free(buf);
        return -1;
    }
    is64 = id[4] == 2;
    big = id[5] == 2;
    phoff = is64 ? get(buf + 32, 8, big) : get(buf + 28, 4, big);
    phentsize = get(buf + (is64 ? 54 : 42), 2, big);
    phnum = get(buf + (is64 ? 56 : 44), 2, big);
    for (i = 0; i < phnum && rc == 0; i++)
    {
        const uint8_t   *ph = buf + phoff + i * phentsize;
        uint64_t        type, off, vaddr, paddr, filesz, memsz, k;

        if ((uint64_t) (ph - buf) + phentsize > (uint64_t) len)
        {
            fprintf(stderr, "%s: truncated program header\n", path);
            rc = -1;
            break;
        }
        type = get(ph, 4, big);
        if (type != 1)                  /* PT_LOAD */
        {
            continue;
        }
        if (is64)
        {
            off = get(ph + 8, 8, big);
            vaddr = get(ph + 16, 8, big);
            paddr = get(ph + 24, 8, big);
            filesz = get(ph + 32, 8, big);
            memsz = get(ph + 40, 8, big);
        }
        else
        {
            off = get(ph + 4, 4, big);
            vaddr = get(ph + 8, 4, big);
            paddr = get(ph + 12, 4, big);
            filesz = get(ph + 16, 4, big);
            memsz = get(ph + 20, 4, big);
        }
        (void) vaddr;
        if (paddr < UINT64_C(0x100000000))
        {
            paddr += elf_offset;
        }
        if (off + filesz > (uint64_t) len)
        {
            fprintf(stderr, "%s: segment %llu goes past the end of the file\n", path, (unsigned long long) i);
            rc = -1;
            break;
        }
        for (k = 0; k < memsz; k++)
        {
            uint8_t *p = byte_at(s, paddr + k);

            /* a segment that starts at offset 0 maps the ELF header and the program headers just before the code :
             * they are not part of the program */
            if (off + k < phoff + phnum * phentsize && off == 0)
            {
                continue;
            }

            if (p == NULL)
            {
                fprintf(stderr, "%s: segment %llu: address 0x%llX is in no memory\n", path,
                        (unsigned long long) i, (unsigned long long) (paddr + k));
                rc = -1;
                break;
            }
            *p = k < filesz ? buf[off + k] : 0;
        }
    }
    free(buf);
    return rc;
}
