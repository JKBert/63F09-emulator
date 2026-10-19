"""VHDL front-end for the translator, built on libghdl (GHDL 4.1.0).

GHDL parses and fully analyses the design (types, overloads, widths), the
translator only walks the typed tree it returns.

Environment:
    VHDL2C_GHDL_SRC      GHDL source tree (provides the pyGHDL package)
    VHDL2C_GHDL_PREFIX   GHDL install prefix (provides libghdl and the std/ieee libraries)
"""

import glob
import os
import sys


def _setup_paths():
    src = os.environ.get("VHDL2C_GHDL_SRC")
    prefix = os.environ.get("VHDL2C_GHDL_PREFIX")
    if not src or not prefix:
        raise SystemExit("set VHDL2C_GHDL_SRC and VHDL2C_GHDL_PREFIX (see tools/vhdl2c/README.md)")
    sys.path.insert(0, src)
    os.environ["GHDL_PREFIX"] = os.path.join(prefix, "lib", "ghdl")
    ld = os.path.join(prefix, "lib")
    if ld not in os.environ.get("LD_LIBRARY_PATH", "").split(":"):
        os.environ["LD_LIBRARY_PATH"] = ld + ":" + os.environ.get("LD_LIBRARY_PATH", "")
        os.execv(sys.executable, [sys.executable] + sys.argv)


_setup_paths()

from pyGHDL import libghdl  # noqa: E402
from pyGHDL.libghdl import errorout_console, libraries, name_table  # noqa: E402
from pyGHDL.libghdl.vhdl import nodes  # noqa: E402

OPTIONS = ("--std=08", "-frelaxed", "-fsynopsys")


class AnalysisError(Exception):
    pass


def init():
    errorout_console.Install_Handler()
    libghdl.initialize()
    for opt in OPTIONS:
        libghdl.set_option(opt)
    if libghdl.analyze_init_status() != 0:
        raise AnalysisError("cannot initialise libghdl")


def analyze(library, path):
    """Analyse one file into the given library (lower case) and return its design file node."""
    libraries.Work_Library_Name.value = name_table.Get_Identifier(library)
    libraries.Load_Work_Library(False)
    design_file = libghdl.analyze_file(path)
    if not design_file:
        raise AnalysisError("analysis failed: " + path)
    return design_file


def analyze_files(files):
    """files : list of (library, path) in compilation order. Returns the design file nodes."""
    return [analyze(lib, path) for lib, path in files]


def units(design_file):
    unit = nodes.Get_First_Design_Unit(design_file)
    while unit:
        yield unit
        unit = nodes.Get_Chain(unit)


def ident(node):
    return name_table.Get_Name_Ptr(nodes.Get_Identifier(node))


def find_files(directory, names):
    """Resolve '63F09' to <directory>/*-63F09.vhd (upload naming) or <directory>/63F09.vhd."""
    result = {}
    for name in names:
        hits = glob.glob(os.path.join(directory, "*-%s.vhd" % name)) + glob.glob(os.path.join(directory, "%s.vhd" % name))
        if len(hits) != 1:
            raise AnalysisError("expected one file for %s in %s, found %d" % (name, directory, len(hits)))
        result[name] = hits[0]
    return result
