# Building the emulator

    make emu                  # build/soc63f09, from the generated C : no VHDL, no GHDL, no Python needed
    make emu ATOMIC=1         # the same, with C11 atomics for the barrier of the threads (see THREADS.md)
    make test-soc             # smoke tests of the emulator
    make test-rt              # unit tests of the runtime and of the EEPROM model
    make clean                # the object files ; make distclean removes build/

What `make emu` needs : `make`, a C99 compiler (`cc`) and POSIX threads, on a 64-bit system (the simulation state lives in
an arena mapped at a fixed address, 0x200000000000, see `docs/THREADS.md` and `src/soc/snapshot.c`).

## The flags

Default, in the `Makefile` :

| | |
|---|---|
| `CFLAGS` | `-std=c99 -O2 -Wall -Wextra -fno-pie -pthread` (`-std=gnu11 -DVS_C11_ATOMICS ...` with `ATOMIC=1`) |
| `CPPFLAGS` | `-D_POSIX_C_SOURCE=200809L -Isrc/rt` (the includes of `src/`, `src/gen` and `src/rt` are added for the emulator) |
| link | `$(CC) $(CFLAGS) -no-pie` |

- `-fno-pie` and `-no-pie` : a snapshot (`--save`, `--restore`) holds pointers to the code (timers, processes), so the
  executable must be loaded at the same address each time. Without them a snapshot cannot be restored.
- `-pthread` : the threads of `--threads` (POSIX).
- `-D_POSIX_C_SOURCE=200809L` : with `-std=c99` it exposes the POSIX functions (threads, spin locks, `sigaction`, `mmap`).
- `ATOMIC=1` : replaces the POSIX barrier by one made of C11 atomics (ISO C, not POSIX) : 3 to 10 times cheaper, which
  matters because a delta cycle lasts a few microseconds. The result of the simulation does not change.
- `-O2` : the speed matters (about 50 to 80 million ticks per second with one core on a 2.8 GHz Xeon). `-O3` or `-march=native` can be
  tried, they were not measured.

## Variables

They can be set on the command line (`make emu CC=clang`) or in the environment.

| Variable | Default | Meaning |
|---|---|---|
| `CC` | `cc` | the C compiler |
| `CFLAGS` | see above | **replaces** the default flags : keep `-fno-pie -pthread` (and `-std`) when you set it |
| `CPPFLAGS` | see above | added to (`+=`), the POSIX definition is kept |
| `ATOMIC` | unset | any value : the barrier with C11 atomics, and `-std=gnu11` |
| `BUILD` | `build` | the directory of the objects and of the executable |
| `VHDL_DIR` | empty | the directory of the VHDL files (`make gen`, `make test`, `make cosim`) |
| `PYTHON`, `VENV`, `GHDL`, `GHDL_TAG`, `GHDL_SRC`, `GHDL_INSTALL` | in `build/` | the tools of the translator, see `docs/GENERATION.md` |

Examples :

    make emu CC=clang
    make emu ATOMIC=1 CFLAGS='-std=gnu11 -DVS_C11_ATOMICS -O3 -fno-pie -pthread'
    make emu BUILD=/tmp/emu-build

After a change of `CFLAGS` or `ATOMIC`, run `make clean` first : the objects are not rebuilt when only the flags change.

## Regenerating the C from the VHDL

    make tools                                     # once : GHDL 4.1.0 and the Python environment
    make gen VHDL_DIR=/path/to/vhdl                # src/gen, src/gen/memmap.h and docs/MEMORY_MAP.md
    make test VHDL_DIR=/path/to/vhdl               # every block against GHDL (about 30 minutes)
    make cosim VHDL_DIR=/path/to/vhdl ELF=prog.elf # the whole SoC against GHDL

`make gen` is the only way to produce `src/gen` : never edit it by hand. See `docs/GENERATION.md`.

## Other systems

Only POSIX is used by the default build (`pthread_*`, `sched_yield`, `mmap`, `sigaction`). It was built and tested on Linux
only ; for NetBSD and the others nothing is known to prevent it, but it was not tried.
