/* Command line of the emulator of the 63F09 system on chip. */

#include <getopt.h>
#include <stdlib.h>
#include <string.h>

#include "soc/soc.h"
#include "soc/snapshot.h"

static void usage(FILE *f)
{
    fprintf(f,
        "usage: soc63f09 [options]\n"
        "  --ncpus N            number of cores, 1 to 8 (default 2, as SoC.vhd)\n"
        "  --fpu by-core|shared one FPU per core, or one shared by all the cores (default shared, as SoC.vhd)\n"
        "  --ext BASE:SIZE      a memory of the external bus, standing for the companion (several allowed ;\n"
        "                       default 0xF00000000:0x1000000)\n"
        "  --elf FILE           load the segments of an ELF file : ROM and internal RAM at their\n"
        "                       addresses (docs/MEMORY_MAP.md), the rest in the external memories. Addresses below 4 GiB get\n"
        "                       the offset 0xF00000000, the physical address when the MMU is off\n"
        "  --elf-offset ADDR    change that offset\n"
        "  --acia N[,baud=B][,in=FILE|-|none][,out=FILE|-|none]\n"
        "                       the serial line of ACIA N (0 or 1) goes to the console : \"-\" is stdin for in\n"
        "                       and stdout for out ; default baud 115200. B is the rate of the host side : the\n"
        "                       program must set the same one in the ACIA (divider /16 : 24e6 / (16 * (div + 1)))\n"
        "                       socket=PATH replaces in/out by a Unix domain socket the emulator listens on\n"
        "                       (one peer at a time, raw bytes) ; wait blocks until a peer connects\n"
        "  --spi-slave          a SPI slave (mode 0) on SS0 that answers each byte with the previous one\n"
        "  --pins PATH[,wait]   the pins of the PIA, PTM, SPI, TWI and the interrupt inputs on a Unix socket (text lines,\n"
        "                       see src/soc/pins.h and docs/EMULATOR.md) ; wait blocks until a peer connects\n"
        "  --twi-eeprom ADDR[,file=PATH][,wr=US][,page=N]\n"
        "                       an I2C EEPROM (24C02 like, 256 bytes) with the 7-bit address ADDR on the TWI pins ; file : its\n"
        "                       content is read from PATH at the start and written back after each write ; wr : write cycle in\n"
        "                       microseconds of simulated time (24C02 : 5000), the EEPROM does not answer meanwhile ; page : bytes\n"
        "                       of a write page, a power of 2 (24C02 : 8), a sequential write wraps inside it\n"
        "  --peek-eeprom        print the content of the EEPROM when the run ends\n"
        "  --reset-us N         RESET_n stays low N microseconds (default 5 ; the peripherals need E to run during the reset)\n"
        "  --threads N          each core (with its MMU and DMC) is a partition of its own, run by N threads (0 : the whole\n"
        "                       design in one kernel, the default)\n"
        "  --save FILE          write a snapshot of the whole state when the run ends (or at --save-at)\n"
        "  --save-at N          write the snapshot at N ticks (the run goes on)\n"
        "  --restore FILE       start from a snapshot made by this same executable (--ticks is then the absolute time\n"
        "                       to stop at ; the serial lines, pins and files are those of this command line ;\n"
        "                       --ncpus, --ext, --elf and the other options of the machine come from the snapshot)\n"
        "  --ticks N            stop after N ticks of simulated time (a tick is 1/144 ns ; default 100000000, about 0.7 ms ;\n"
        "                       0 : no limit, the run goes on until the program calls finish, or Ctrl-C / SIGTERM, which stop it\n"
        "                       cleanly: the sockets are closed and the snapshot of --save is written)\n"
        "  --dump FILE          write every change of every named signal\n"
        "  --peek ADDR:LEN      print LEN bytes of memory at the physical address ADDR when the run ends\n"
        "  --trace-bus          print the cycles of the external bus\n"
        "  --trap-unmapped      stop at the first cycle of the external bus that no --ext memory answers\n"
        "                       (the first one is always reported on stderr)\n"
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
        { "spi-slave", no_argument, NULL, 'S' },
        { "twi-eeprom", required_argument, NULL, 'E' },
        { "pins", required_argument, NULL, 'I' },
        { "peek-eeprom", no_argument, NULL, 'P' },
        { "reset-us", required_argument, NULL, 'R' },
        { "ticks", required_argument, NULL, 't' },
        { "threads", required_argument, NULL, 'H' },
        { "save", required_argument, NULL, 'V' },
        { "save-at", required_argument, NULL, 'A' },
        { "restore", required_argument, NULL, 'L' },
        { "dump", required_argument, NULL, 'd' },
        { "peek", required_argument, NULL, 'k' },
        { "trace-bus", no_argument, NULL, 'T' },
        { "trap-unmapped", no_argument, NULL, 'U' },
        { "help", no_argument, NULL, 'h' },
        { NULL, 0, NULL, 0 }
    };
    soc_cfg     cfg;
    soc         *s;
    const char  *elf = NULL;
    const char  *restore = NULL;
    uint64_t    peek_addr = 0, peek_len = 0;
    int         peek_eeprom = 0;
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
            case 'S':
                cfg.spi_slave = 1;
                break;
            case 'I':
            {
                char *comma = strchr(optarg, ',');

                if (comma != NULL)
                {
                    cfg.pins_wait = strcmp(comma + 1, "wait") == 0;
                    *comma = '\0';
                }
                snprintf(cfg.pins_socket, sizeof(cfg.pins_socket), "%s", optarg);
                break;
            }
            case 'E':
                cfg.twi_eeprom = 1;
                cfg.twi_eeprom_addr = (unsigned) strtoul(optarg, NULL, 0) & 0x7F;
                {
                    char *opt = strchr(optarg, ',');

                    while (opt != NULL)
                    {
                        opt++;
                        if (strncmp(opt, "file=", 5) == 0)
                        {
                            snprintf(cfg.twi_eeprom_file, sizeof(cfg.twi_eeprom_file), "%.*s", (int) strcspn(opt + 5, ","), opt + 5);
                        }
                        else if (strncmp(opt, "wr=", 3) == 0)
                        {
                            cfg.twi_eeprom_write_us = (unsigned) strtoul(opt + 3, NULL, 0);
                        }
                        else if (strncmp(opt, "page=", 5) == 0)
                        {
                            cfg.twi_eeprom_page = (unsigned) strtoul(opt + 5, NULL, 0);
                        }
                        opt = strchr(opt, ',');
                    }
                }
                break;
            case 'P':
                peek_eeprom = 1;
                break;
            case 'R':
                cfg.reset_ticks = (uint64_t) (strtod(optarg, NULL) * 144000.0 + 0.5);
                break;
            case 't':
                cfg.max_ticks = strtoull(optarg, NULL, 0);
                break;
            case 'H':
                cfg.threads = atoi(optarg);
                break;
            case 'V':
                snprintf(cfg.save_path, sizeof(cfg.save_path), "%s", optarg);
                break;
            case 'A':
                cfg.save_at = strtoull(optarg, NULL, 0);
                break;
            case 'L':
                restore = optarg;
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
            case 'U':
                cfg.trap_unmapped = 1;
                break;
            case 'T':
                cfg.trace_bus = 1;
                break;
            default:
                usage(opt == 'h' ? stdout : stderr);
                return opt == 'h' ? 0 : 2;
        }
    }
    if (restore != NULL)
    {
        if (elf != NULL)
        {
            fprintf(stderr, "--elf and --restore cannot be used together\n");
            return 2;
        }
        s = snapshot_load(restore);
        if (s == NULL || soc_rehost(s, &cfg) != 0)
        {
            return 1;
        }
    }
    else
    {
        if (cfg.nzones == 0)
        {
            soc_add_zone(&cfg, UINT64_C(0xF00000000), 0x1000000);
        }
        s = vs_arena_alloc(sizeof(*s));
        if (soc_create(s, &cfg) != 0)
        {
            return 1;
        }
        if (elf != NULL && soc_load_elf(s, elf) != 0)
        {
            return 1;
        }
    }
    soc_run(s);
    printf("time %llu ticks, %llu external reads, %llu external writes, %llu of the external cycles unmapped\n",
           (unsigned long long) s->k.now, (unsigned long long) s->reads, (unsigned long long) s->writes,
           (unsigned long long) s->unmapped);
    if (getenv("VS_STATS") != NULL)
    {
        unsigned pp;

        fprintf(stderr, "%llu delta cycles ; processes run: %llu, sum over the deltas of the busiest partition: %llu\n",
                (unsigned long long) s->k.deltas, vs_stat_tot, vs_stat_max);
        for (pp = 0; pp < s->k.nparts; pp++)
        {
            fprintf(stderr, "partition %u : %llu processes run\n", pp, vs_stat_runs[pp]);
        }
    }
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
    if (peek_eeprom && cfg.twi_eeprom)
    {
        int i;

        printf("eeprom (%u starts, %u stops, %u bytes written, %u read):\n", s->eeprom.starts, s->eeprom.stops,
               s->eeprom.writes, s->eeprom.reads);
        for (i = 0; i < 256; i++)
        {
            printf("%s%02X", i % 16 ? " " : (i ? "\n" : ""), s->eeprom.mem[i]);
        }
        printf("\n");
    }
    soc_destroy(s);
    return 0;
}
