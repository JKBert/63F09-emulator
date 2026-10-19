# vhdl2c

Translator from the 63F09 VHDL sources to C. GHDL (libghdl) parses and analyses the
VHDL, so every expression arrives typed and every call resolved ; the translator walks
that tree and emits C. Only the generated C is needed to build the emulator : GHDL is
a build-time dependency of the translator, never of the emulator.

The VHDL sources are not public and are never stored in this repository.

## Setting up GHDL (once)

Needs GNAT, `make` and zlib (`apt-get install gnat make zlib1g-dev`).

    git clone --depth 1 --branch v4.1.0 https://github.com/ghdl/ghdl ghdl-src
    cd ghdl-src && ./configure --prefix=$PWD/../ghdl-install && make -j && make install
    pip install pyTooling

Then :

    export VHDL2C_GHDL_SRC=/path/to/ghdl-src
    export VHDL2C_GHDL_PREFIX=/path/to/ghdl-install

## Tools

- `frontend.py` : loads the sources into GHDL libraries in compilation order.
- `dump.py <vhdl dir> <unit> [depth]` : prints the typed tree of a design unit.
