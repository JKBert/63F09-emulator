/* Command line of the emulator of the 63F09 system on chip. */

#include <getopt.h>
#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"

static void usage(FILE *f)
{
    fprintf(f,
        "usage: soc63f09 [options]\n"
        "  --ncpus N            number of cores, 1 to 8 (default 1)\n"
        "  --fpu by-core|shared one FPU per core, or one shared by all the cores (default by-core)\n"
        "  --ram BASE:SIZE      add a RAM zone (several allowed ; default 0xF00000000:0x10000)\n"
        "  --rom BASE:SIZE      add a ROM zone (several allowed ; default 0xFFFFF0000:0x10000)\n"
        "  --elf FILE           load the segments of an ELF file into the zones (addresses below 4 GiB get\n"
        "                       the offset 0xF00000000, the physical address when the MMU is off)\n"
        "  --elf-offset ADDR    change that offset\n"
        "  --acia BASE[,baud=N][,in=FILE|-][,out=FILE|-]\n"
        "                       an ACIA at BASE (4 bytes) whose serial line goes to the console : \"-\" is\n"
        "                       stdin for in and stdout for out ; default baud 115200, default in=- out=-\n"
        "  --bac-base ADDR      registers of the bus arbiter (default 0xFFFFE0000)\n"
        "  --mmu-base ADDR      registers of the MMUs (default 0xFFFFE1000)\n"
        "  --ticks N            stop after N ticks (a tick is 1/144 ns ; default 100000000)\n"
        "  --trace-bus          print every bus cycle\n"
        "  --help\n");
}

static int acia_arg(soc_cfg *c, char *arg)
{
    soc_acia_cfg    *a;
    char            *tok;
    FILE            *in = stdin, *out = stdout;
    unsigned        baud = 115200;

    if (c->nacias == SOC_MAX_ACIAS)
    {
        return -1;
    }
    tok = strtok(arg, ",");
    a = &c->acias[c->nacias];
    a->base = strtoull(tok, NULL, 0);
    while ((tok = strtok(NULL, ",")) != NULL)
    {
        if (strncmp(tok, "baud=", 5) == 0)
        {
            baud = (unsigned) strtoul(tok + 5, NULL, 0);
        }
        else if (strncmp(tok, "in=", 3) == 0)
        {
            in = strcmp(tok + 3, "-") == 0 ? stdin : (strcmp(tok + 3, "none") == 0 ? NULL : fopen(tok + 3, "r"));
            if (in == NULL && strcmp(tok + 3, "none") != 0)
            {
                perror(tok + 3);
                return -1;
            }
        }
        else if (strncmp(tok, "out=", 4) == 0)
        {
            out = strcmp(tok + 4, "-") == 0 ? stdout : (strcmp(tok + 4, "none") == 0 ? NULL : fopen(tok + 4, "w"));
            if (out == NULL && strcmp(tok + 4, "none") != 0)
            {
                perror(tok + 4);
                return -1;
            }
        }
        else
        {
            return -1;
        }
    }
    if (baud == 0)
    {
        return -1;
    }
    a->baud = baud;
    a->in = in;
    a->out = out;
    c->nacias++;
    return 0;
}

static int zone_arg(soc_cfg *c, const char *arg, int writable)
{
    char        *end;
    uint64_t    base = strtoull(arg, &end, 0);
    uint64_t    size;

    if (*end != ':')
    {
        return -1;
    }
    size = strtoull(end + 1, &end, 0);
    if (*end != '\0')
    {
        return -1;
    }
    return soc_add_zone(c, base, size, writable);
}

int main(int argc, char **argv)
{
    static const struct option options[] =
    {
        { "ncpus", required_argument, NULL, 'n' },
        { "fpu", required_argument, NULL, 'f' },
        { "ram", required_argument, NULL, 'r' },
        { "rom", required_argument, NULL, 'o' },
        { "elf", required_argument, NULL, 'e' },
        { "elf-offset", required_argument, NULL, 'O' },
        { "acia", required_argument, NULL, 'a' },
        { "bac-base", required_argument, NULL, 'b' },
        { "mmu-base", required_argument, NULL, 'm' },
        { "ticks", required_argument, NULL, 't' },
        { "trace-bus", no_argument, NULL, 'T' },
        { "help", no_argument, NULL, 'h' },
        { NULL, 0, NULL, 0 }
    };
    soc_cfg     cfg;
    soc         *s;
    const char  *elf = NULL;
    int         opt, nz = 0;

    soc_cfg_default(&cfg);
    cfg.max_ticks = 100000000;
    while ((opt = getopt_long(argc, argv, "h", options, NULL)) != -1)
    {
        switch (opt)
        {
            case 'n':
                cfg.ncpus = atoi(optarg);
                break;
            case 'f':
                if (strcmp(optarg, "shared") == 0)
                {
                    cfg.fpu_shared = 1;
                }
                else if (strcmp(optarg, "by-core") == 0)
                {
                    cfg.fpu_shared = 0;
                }
                else
                {
                    usage(stderr);
                    return 2;
                }
                break;
            case 'r':
            case 'o':
                if (zone_arg(&cfg, optarg, opt == 'r') != 0)
                {
                    fprintf(stderr, "bad zone: %s\n", optarg);
                    return 2;
                }
                nz++;
                break;
            case 'a':
                if (acia_arg(&cfg, optarg) != 0)
                {
                    fprintf(stderr, "bad ACIA: %s\n", optarg);
                    return 2;
                }
                break;
            case 'e':
                elf = optarg;
                break;
            case 'O':
                cfg.elf_offset = strtoull(optarg, NULL, 0);
                break;
            case 'b':
                cfg.bac_base = strtoull(optarg, NULL, 0);
                break;
            case 'm':
                cfg.mmu_base = strtoull(optarg, NULL, 0);
                break;
            case 'T':
                cfg.trace_bus = 1;
                break;
            case 't':
                cfg.max_ticks = strtoull(optarg, NULL, 0);
                break;
            default:
                usage(opt == 'h' ? stdout : stderr);
                return opt == 'h' ? 0 : 2;
        }
    }
    if (nz == 0)
    {
        soc_add_zone(&cfg, UINT64_C(0xF00000000), 0x10000, 1);
        soc_add_zone(&cfg, UINT64_C(0xFFFFF0000), 0x10000, 0);
    }
    s = malloc(sizeof(*s));
    if (s == NULL || soc_create(s, &cfg) != 0)
    {
        return 1;
    }
    if (elf != NULL && soc_load_elf(s, elf) != 0)
    {
        return 1;
    }
    soc_run(s);
    printf("time %llu ticks, %llu reads, %llu writes, %llu unmapped\n", (unsigned long long) s->k.now,
           (unsigned long long) s->reads, (unsigned long long) s->writes, (unsigned long long) s->unmapped);
    soc_destroy(s);
    free(s);
    return 0;
}
