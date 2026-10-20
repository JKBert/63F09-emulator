/* Command line of the emulator of the 63F09 system on chip. */

#include <getopt.h>
#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"

static void usage(FILE *f)
{
    fprintf(f,
        "usage: soc63f09 [options]\n"
        "  --ncpus N            number of cores, 1 to 8 (default 2, as SoC.vhd)\n"
        "  --fpu by-core|shared one FPU per core, or one shared by all the cores (default shared, as SoC.vhd)\n"
        "  --ext BASE:SIZE      a memory of the external bus, standing for the companion (several allowed ;\n"
        "                       default 0xF00000000:0x1000000)\n"
        "  --elf FILE           load the segments of an ELF file : ROM at 0xFFFFF0000, internal RAM at\n"
        "                       0xFFFFC0000, the rest in the external memories. Addresses below 4 GiB get\n"
        "                       the offset 0xF00000000, the physical address when the MMU is off\n"
        "  --elf-offset ADDR    change that offset\n"
        "  --acia N[,baud=B][,in=FILE|-|none][,out=FILE|-|none]\n"
        "                       the serial line of ACIA N (0 or 1) goes to the console : \"-\" is stdin for in\n"
        "                       and stdout for out ; default baud 115200. B is the rate of the host side : the\n"
        "                       program must set the same one in the ACIA (divider /16 : 24e6 / (32 * (div + 1)))\n"
        "                       socket=PATH replaces in/out by a Unix domain socket the emulator listens on\n"
        "                       (one peer at a time, raw bytes) ; wait blocks until a peer connects\n"
        "  --ticks N            stop after N ticks (a tick is 1/144 ns ; default 100000000)\n"
        "  --dump FILE          write every change of every named signal\n"
        "  --peek ADDR:LEN      print LEN bytes of memory at the physical address ADDR when the run ends\n"
        "  --trace-bus          print the cycles of the external bus\n"
        "  --help\n");
}

static int acia_arg(soc_cfg *c, char *arg)
{
    soc_serial      *a;
    char            *tok;
    FILE            *in = stdin, *out = stdout;
    unsigned        baud = 115200;
    unsigned long   n;

    tok = strtok(arg, ",");
    n = strtoul(tok, NULL, 0);
    if (n >= SOC_NACIA)
    {
        return -1;
    }
    a = &c->serial[n];
    memset(a, 0, sizeof(*a));
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
        else if (strncmp(tok, "socket=", 7) == 0)
        {
            snprintf(a->socket, sizeof(a->socket), "%s", tok + 7);
        }
        else if (strcmp(tok, "wait") == 0)
        {
            a->wait = 1;
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
    a->enabled = 1;
    a->baud = baud;
    a->in = in;
    a->out = out;
    return 0;
}

static int zone_arg(soc_cfg *c, const char *arg)
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
    return soc_add_zone(c, base, size);
}

int main(int argc, char **argv)
{
    static const struct option options[] =
    {
        { "ncpus", required_argument, NULL, 'n' },
        { "fpu", required_argument, NULL, 'f' },
        { "ext", required_argument, NULL, 'x' },
        { "elf", required_argument, NULL, 'e' },
        { "elf-offset", required_argument, NULL, 'O' },
        { "acia", required_argument, NULL, 'a' },
        { "ticks", required_argument, NULL, 't' },
        { "dump", required_argument, NULL, 'd' },
        { "peek", required_argument, NULL, 'k' },
        { "trace-bus", no_argument, NULL, 'T' },
        { "help", no_argument, NULL, 'h' },
        { NULL, 0, NULL, 0 }
    };
    soc_cfg     cfg;
    soc         *s;
    const char  *elf = NULL;
    uint64_t    peek_addr = 0, peek_len = 0;
    int         opt;

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
            case 'x':
                if (zone_arg(&cfg, optarg) != 0)
                {
                    fprintf(stderr, "bad memory: %s\n", optarg);
                    return 2;
                }
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
            case 't':
                cfg.max_ticks = strtoull(optarg, NULL, 0);
                break;
            case 'd':
                cfg.dump = fopen(optarg, "w");
                if (cfg.dump == NULL)
                {
                    perror(optarg);
                    return 2;
                }
                break;
            case 'k':
                peek_addr = strtoull(optarg, NULL, 0);
                if (strchr(optarg, ':') != NULL)
                {
                    peek_len = strtoull(strchr(optarg, ':') + 1, NULL, 0);
                }
                break;
            case 'T':
                cfg.trace_bus = 1;
                break;
            default:
                usage(opt == 'h' ? stdout : stderr);
                return opt == 'h' ? 0 : 2;
        }
    }
    if (cfg.nzones == 0)
    {
        soc_add_zone(&cfg, UINT64_C(0xF00000000), 0x1000000);
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
    printf("time %llu ticks, %llu external reads, %llu external writes, %llu unmapped\n",
           (unsigned long long) s->k.now, (unsigned long long) s->reads, (unsigned long long) s->writes,
           (unsigned long long) s->unmapped);
    if (peek_len > 0)
    {
        uint64_t i;

        for (i = 0; i < peek_len; i++)
        {
            uint8_t *b = soc_byte(s, peek_addr + i);

            if (i % 16 == 0)
            {
                printf("%s%09llX:", i ? "\n" : "", (unsigned long long) (peek_addr + i));
            }
            if (b != NULL)
            {
                printf(" %02X", *b);
            }
            else
            {
                printf(" --");
            }
        }
        printf("\n");
    }
    soc_destroy(s);
    free(s);
    return 0;
}
