# Threads

`--threads N` runs the emulator with N threads. The default, `--threads 0`, is the single kernel that all the tests and
the measurements of `docs/EMULATOR.md` use. This file says how the threads work, what they cost and what they give.

## Partitions

The design is cut in **partitions**. Partition 0 is the system on chip: the bus arbiter (BAC) with the shared FPU, the
peripherals, the memories, the clocks. Partitions 1 to NCPUS are the cores: each `DMC_63F41` (CPU, MMU, caches) is one.
With `FPU_BY_CORE` the FPU is a part of the 63F09 and belongs to the partition of its core, without it the FPU is in
the BAC, i.e. in partition 0. Partition 0 is run by the thread that calls the kernel, the cores are shared among the
other threads (`--threads N` means N threads in all).

* Every signal and every process belongs to the partition that was current when it was created
  (`vs_part_enter`, called by the generated code of the BAC around the creation of a DMC).
* A process reads and writes the signals of its partition only. The ports of a DMC are signals of the core's
  partition, tied (zero-delay `vs_tie_fields`) to the signals of the BAC they are connected to (generator:
  `threaded_instance` in `tools/vhdl2c/gen.py`). Without `--threads` the ports are the signals of the BAC itself and
  nothing changes.
* A tie that reaches another partition is not followed by the commit: its new value is queued for that partition,
  which takes it before the next delta cycle. A process of another partition that a signal wakes goes to the mail of
  that partition. A chain (a tie that leads to a tie that leaves the partition: the snoop of the caches goes from a
  core to the BAC and from there to the other cores) needs one more round; this is decided by the barrier.
* An event is a change in the last commit: it is stamped with the generation of the commit (`vs_gen`) so nothing has to be
  cleared after the processes have run.

A delta cycle is: every thread runs the processes of its partitions, commits its pending values, **barrier**, takes what
the others left for it. One barrier per delta cycle. The result is the same as in the single kernel (the same delta
cycles, the same order of the commit), which `tests/soc/run.sh` checks on the bus trace and `tests/ghdl/cosim.py`
checks against GHDL (`COSIM_EMU` with a wrapper that adds `--threads 3`).

`--threads 1` runs the partitions one after the other in the calling thread: it checks the cut without the threads.

## `--ncpus` and `--threads`

`--ncpus N` is the machine: the number of cores that are emulated (1 to 8). `--threads T` is how the host runs it: the
number of threads of the process. They do not depend on each other: 8 cores can be run by 1 thread, 2 cores by 3.

| `--threads` | What happens |
|---|---|
| 0 (default) | One kernel, one partition, one thread. The ports of a DMC are the signals of the BAC. The reference of the tests and of the measures. |
| 1 | The cores are partitions of their own (ports tied to the signals of the BAC) but **no thread is created**: the calling thread runs the partitions one after the other. The bus trace is the same as with 0, the speed too. It checks the cut, and a snapshot made so can be restored with `--threads` > 1. |
| T ≥ 2 | T threads in all. The calling thread runs partition 0 (the SoC), the T - 1 others share the partitions of the cores. |

The partition of core c is the partition c + 1. The partitions of the cores are given to the T - 1 threads in turn: the
partition p goes to thread 1 + (p - 1) mod (T - 1). With more threads than partitions, T becomes NCPUS + 1 (a thread has
nothing to do otherwise). `VS_STATS=1` prints who runs what.

| Command | Thread 0 | Thread 1 | Thread 2 | Others |
|---|---|---|---|---|
| `--ncpus 5 --threads 2` | SoC | cores 0 to 4 | | |
| `--ncpus 7 --threads 3` | SoC | cores 0, 2, 4, 6 | cores 1, 3, 5 | |
| `--ncpus 8 --threads 9` | SoC | core 0 | core 1 | one thread for each of the cores 2 to 7 |
| `--ncpus 8 --threads 20` | as 9: 9 threads | | | |

**`--threads 3 --ncpus 7`** : two threads for 7 cores cannot share them equally. Thread 1 runs 4 cores and thread 2 runs 3.
A delta cycle ends when the slowest thread has finished, so thread 1 sets the pace and thread 2 waits at the barrier about
a quarter of the time: the gain is that of 4 cores in a thread, not of 3.5. With 7 cores the useful values of `--threads` are
2 (all the cores in one thread, parallel with the SoC), 8 (one thread per core), or 3 to 7 knowing that some threads have
one core more than others (a divisor of the number of cores, plus 1, balances: 4 threads for 6 cores, 5 for 8 cores,
or 3 for 4 cores).
The result of the simulation is the same for every value (bus trace identical, checked for `--ncpus 7 --threads=3`
among others): only the speed changes.

Whatever the value, one thread needs one processor: with more threads than processors the run is much slower (the
threads wait in the barrier, see Limits).

## What is used

POSIX only for the default build: `pthread_create`/`pthread_join`, `pthread_spin_*` for the barrier (a mutex and a
condition variable when the system has no spin locks), `sched_yield` in the wait loop. No futex, no processor
instruction, no affinity (pin the process from outside: `taskset` on Linux, `cpuctl` on NetBSD, `psrset` on Solaris).
The memory is synchronised by the lock calls, as POSIX says (4.12).

`make emu ATOMIC=1` builds the barrier with C11 atomics (ISO C, not POSIX): one counter and one generation flag. It is
3 to 10 times cheaper than the POSIX barrier, which matters because a delta cycle lasts about 2 to 8 µs.

## Measures (a Xeon at 2.8 GHz, 4 virtual processors)

`allcores.elf` starts all the cores, each one loops in its cache (`tests/soc/bench.sh`). Seconds for 30 million ticks:

| Cores | One kernel | `--threads N+1`, POSIX barrier | `--threads N+1`, ATOMIC=1 |
|---|---|---|---|
| 1 | 1.47 | 2.3 | 1.49 |
| 2 | 2.38 | 5.4 | 2.80 |
| 3 | 4.34 | 10.5 | 4.48 |

Barrier alone (micro benchmark, 2/3/4 threads): POSIX spin locks 0.7/2.0/4.1 µs, C11 atomics 0.21/0.24/0.42 µs. A cache
line goes from a core to another and back in 112 ns on this machine.

**No gain here.** The reason is in the work: a delta cycle runs about 45 processes (1 core) to 130 (8 cores), and the
partitions are not busy at the same time. In the sequential mode, `VS_STATS=1` prints for the whole run the processes run and
the sum, over the delta cycles, of the processes of the busiest partition (the best that threads can do):

| Cores | Processes run | Sum of the busiest partition | Best speed-up |
|---|---|---|---|
| 3 | 35.9 M | 26.8 M | 1.34 |
| 8 | 101.6 M | 33.2 M | 3.06 |

There are about 7.6 delta cycles per period of CPUCLK (400 MHz). So with the cores that run, the threads can give a factor of
2 to 3 at best for 8 cores, less after the barriers (0.2 to 1 µs each), and nothing for 1 or 2 cores. The machine of the
measures has 4 processors: the case of 9 threads (8 cores) was not measured.

## Limits and what could be done

* A thread spins in the barrier: it needs a processor of its own. With more threads than processors the run is very
  slow (`sched_yield` every 20000 turns). A thread that waits for a long time (the program waits for the console) burns a
  processor too; a sleep after a while is not done.
* The snapshots (`--save`, `--restore`) work with the partitions (the lists are in the arena); the threads are
  started again by the run that restores. `--restore --threads N` needs a snapshot made with `--threads`.
* Gains without threads, not done: fewer delta cycles per period (the clock tree of the BAC and of the DMC produces
  most of them), a layout of the signals in memory that follows the partitions, the idle FPU of the BAC (about 8% of the time).
