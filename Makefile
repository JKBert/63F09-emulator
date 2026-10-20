# 63F09 emulator : build, and regeneration of the C from the VHDL sources.
#
#   make help        list the targets
#   make tools       build GHDL (once) and the Python environment of the translator
#   make gen         translate the VHDL entities to C in src/gen   (needs VHDL_DIR)
#   make census      list the VHDL constructs used by the design   (needs VHDL_DIR)
#   make test        compare the C in src/gen to GHDL on random stimuli (needs VHDL_DIR)
#   make test-rt     unit tests of the C runtime (no VHDL needed)
#   make clean       remove the object files ; distclean also removes build/
#
# VHDL_DIR is the directory that holds the VHDL files (the sources are private and are never
# stored in this repository) : VHDL_DIR=/path/to/vhdl make test

BUILD        ?= build
VHDL_DIR     ?=
GHDL_TAG     ?= v4.1.0
GHDL_SRC     ?= $(abspath $(BUILD)/ghdl-src)
GHDL_INSTALL  ?= $(abspath $(BUILD)/ghdl-install)
VENV         ?= $(abspath $(BUILD)/venv)
PYTHON       ?= $(VENV)/bin/python
GHDL         ?= $(GHDL_INSTALL)/bin/ghdl

CC           ?= cc
CFLAGS       ?= -std=c99 -O2 -Wall -Wextra
CPPFLAGS     += -D_POSIX_C_SOURCE=200809L -Isrc/rt

export VHDL2C_GHDL_SRC    := $(GHDL_SRC)
export VHDL2C_GHDL_PREFIX := $(GHDL_INSTALL)

LIBGHDL      := $(GHDL_INSTALL)/lib/libghdl-4_1_0.so
VENV_STAMP   := $(VENV)/.pytooling

.PHONY: all help tools gen census test test-rt clean distclean need-vhdl

all: tools

help:
	@sed -n '2,12p' Makefile

# --- Tools : GHDL provides the typed VHDL tree, pyGHDL gives Python access to it -------------

tools: $(LIBGHDL) $(VENV_STAMP)

$(LIBGHDL):
	@command -v gnatmake >/dev/null || { echo "GNAT is required : apt-get install gnat make zlib1g-dev"; exit 1; }
	mkdir -p $(BUILD)
	test -d $(GHDL_SRC) || git clone --depth 1 --branch $(GHDL_TAG) https://github.com/ghdl/ghdl $(GHDL_SRC)
	cd $(GHDL_SRC) && ./configure --prefix=$(GHDL_INSTALL)
	$(MAKE) -C $(GHDL_SRC)
	$(MAKE) -C $(GHDL_SRC) install

$(VENV_STAMP):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet pyTooling
	touch $@

# --- Using the VHDL ---------------------------------------------------------------------------

need-vhdl:
	@test -n "$(VHDL_DIR)" || { echo "set VHDL_DIR to the directory of the VHDL files"; exit 1; }
	@test -d "$(VHDL_DIR)" || { echo "VHDL_DIR=$(VHDL_DIR) is not a directory"; exit 1; }

# The entities translated to C (see docs/GENERATION.md).
ENTITIES     ?= clk_63f75 wdg_63f46 acia_63f50 amc_63f42 ptm_63f40 pia_63f21 spi_63f52 twi_63f54 mux_74f150 lzc_4 lzc_8 lzc_16 lzc_32 lzc_64 lzc_128 lzc_256 fp_cmp fp_sgnj fp_ext fp_max fp_rnd fp_cvt fp_fma fp_mac fp_fdiv fp_exe fp_unit cpu_63f09 mmu_63f29 dmc_63f41 bac_63f81 soc09

gen: tools need-vhdl
	$(PYTHON) tools/vhdl2c/gen.py $(VHDL_DIR) src/gen $(ENTITIES)

census: tools need-vhdl
	$(PYTHON) tools/vhdl2c/census.py $(VHDL_DIR)

# The emulator : the generated C (src/gen), the hand-written models (src/hand), the runtime (src/rt) and the
# system on chip (src/soc).
EMU_SRC := $(wildcard src/gen/*.c src/hand/*.c src/rt/*.c src/soc/*.c)
EMU_OBJ := $(patsubst src/%.c,$(BUILD)/obj/%.o,$(EMU_SRC))
EMU_CPPFLAGS := $(CPPFLAGS) -Isrc -Isrc/gen -Isrc/rt

emu: $(BUILD)/soc63f09

$(BUILD)/soc63f09: $(EMU_OBJ)
	$(CC) $(CFLAGS) -o $@ $^

$(BUILD)/obj/%.o: src/%.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(EMU_CPPFLAGS) -Wno-unused-parameter -MMD -MP -c -o $@ $<

-include $(EMU_OBJ:.o=.d)

# Each block test compares the C of one entity to GHDL on the same random stimuli.
test: tools need-vhdl
	$(PYTHON) tools/vhdl2c/blocktest.py $(VHDL_DIR) $(GHDL)

# Unit tests of the runtime : no VHDL involved.
test-soc: emu
	sh tests/soc/run.sh $(BUILD)/soc63f09 $(BUILD)/soctest

# Co-simulation of the whole SoC09 : GHDL and the emulator run the same program and the external bus is compared.
# make cosim VHDL_DIR=... ELF=tests/soc/programs/elf/hello.elf [US=20]
ELF ?= tests/soc/programs/elf/hello.elf
US ?= 20
cosim: emu need-vhdl
	$(PYTHON) tests/ghdl/cosim.py $(VHDL_DIR) $(GHDL) $(ELF) $(US)

test-rt:
	mkdir -p $(BUILD)/obj
	$(CC) $(CFLAGS) $(CPPFLAGS) -o $(BUILD)/obj/test_vwide tests/rt/test_vwide.c src/rt/vsim.c
	$(BUILD)/obj/test_vwide

clean:
	$(RM) -r $(BUILD)/obj $(BUILD)/soc63f09

distclean:
	$(RM) -r $(BUILD)
