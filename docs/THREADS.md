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
