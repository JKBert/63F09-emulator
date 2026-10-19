# 63F09 emulator : build, and regeneration of the C from the VHDL sources.
#
#   make help        list the targets
#   make tools       build GHDL (once) and the Python environment of the translator
#   make census      list the VHDL constructs used by the design   (needs VHDL_DIR)
#   make test        compare the C to GHDL on random stimuli       (needs VHDL_DIR)
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

.PHONY: all help tools census test clean distclean need-vhdl

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

census: tools need-vhdl
	$(PYTHON) tools/vhdl2c/census.py $(VHDL_DIR)

# Each test compares the C to GHDL on the same random stimuli.
test: tools need-vhdl
	tests/clk/run_test.sh "$$(ls $(VHDL_DIR)/*63F75.vhd)" $(GHDL)

clean:
	$(RM) -r $(BUILD)/obj

distclean:
	$(RM) -r $(BUILD)
