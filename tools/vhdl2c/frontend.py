"""VHDL front-end for the translator, built on libghdl (GHDL 4.1.0).

GHDL parses and fully analyses the design (types, overloads, widths), the
translator only walks the typed tree it returns.

Environment:
    VHDL2C_GHDL_SRC      GHDL source tree (provides the pyGHDL package)
    VHDL2C_GHDL_PREFIX   GHDL install prefix (provides libghdl and the std/ieee libraries)
"""

import ctypes
import glob
import os
import sys

import compat


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


# ---------------------------------------------------------------------------------------------
# Generic walk of the typed tree
# ---------------------------------------------------------------------------------------------

from pyGHDL.libghdl.vhdl import lists, flists, nodes_meta  # noqa: E402

_Attr = nodes_meta.Attr
_Types = nodes_meta.types
_REF_ATTRS = (_Attr.Ref, _Attr.Forward_Ref, _Attr.Maybe_Forward_Ref, _Attr.Chain_Next)
_LIST_REF_ATTRS = (_Attr.Of_Ref,)


def fields_of(kind):
    first = nodes_meta.get_fields_first(kind)
    last = nodes_meta.get_fields_last(kind)
    for i in range(first, last + 1):
        yield nodes_meta.get_field_by_index(i)


def has_field(kind, field):
    return any(f == field for f in fields_of(kind))


def is_ref(node):
    """True when the node's Maybe_Ref fields are references (flag Is_Ref) and not owned children."""
    kind = nodes.Get_Kind(node)
    return has_field(kind, nodes_meta.fields.Is_Ref) and nodes_meta.Get_Boolean(node, nodes_meta.fields.Is_Ref)


def list_elements(lst):
    """Elements of an Iir_List. pyGHDL's own wrappers pass the iterator by value to functions that
    take it by reference (their `argstype` is a typo for `argtypes`), so the calls are made here."""
    lib = libghdl.libghdl
    ptr = ctypes.POINTER(lists.Iterator)
    lib.vhdl__lists__is_valid.argtypes = [ptr]
    lib.vhdl__lists__is_valid.restype = ctypes.c_bool
    lib.vhdl__lists__next.argtypes = [ptr]
    lib.vhdl__lists__next.restype = None
    lib.vhdl__lists__get_element.argtypes = [ptr]
    lib.vhdl__lists__get_element.restype = ctypes.c_int32
    it = lists.Iterate(lst)
    while lib.vhdl__lists__is_valid(ctypes.byref(it)):
        yield lib.vhdl__lists__get_element(ctypes.byref(it))
        lib.vhdl__lists__next(ctypes.byref(it))


def children(node):
    """Yield (field, child) for the children that `node` owns (references are not followed)."""
    kind = nodes.Get_Kind(node)
    node_is_ref = is_ref(node)
    for field in fields_of(kind):
        ftype = nodes_meta.get_field_type(field)
        attr = nodes_meta.get_field_attribute(field)
        if attr in _REF_ATTRS:
            continue
        if attr in (_Attr.Maybe_Ref, _Attr.Of_Maybe_Ref) and node_is_ref:
            continue
        if ftype == _Types.Iir:
            child = nodes_meta.Get_Iir(node, field)
            if not child:
                continue
            if attr == _Attr.Chain:
                while child:
                    yield field, child
                    child = nodes.Get_Chain(child)
            else:
                yield field, child
        elif ftype == _Types.Iir_Flist and attr not in _LIST_REF_ATTRS:
            fl = nodes_meta.Get_Iir_Flist(node, field)
            if fl > 2:
                for i in range(flists.Length(fl)):
                    child = flists.Get_Nth_Element(fl, i)
                    if child:
                        yield field, child
        elif ftype == _Types.Iir_List and attr not in _LIST_REF_ATTRS:
            lst = nodes_meta.Get_Iir_List(node, field)
            if lst > 1:
                for child in list_elements(lst):
                    if child:
                        yield field, child


def walk(node):
    """Pre-order walk over every owned node below (and including) `node`."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        kids = [c for _, c in children(n)]
        stack.extend(reversed(kids))


def kind_name(node):
    return nodes.Iir_Kind(nodes.Get_Kind(node)).name


def load_project(vhdl_dir, listing):
    """Analyse a project described by `listing` : lines 'library name', where name is a logical
    source name (resolved in vhdl_dir) or '@path' relative to the repository root. Returns the
    design file nodes in order."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    files = []
    for line in open(listing):
        line = line.split("#")[0].strip()
        if not line:
            continue
        lib, name = line.split()
        if name.startswith("@"):
            path = os.path.join(root, name[1:])
        else:
            path = find_files(vhdl_dir, [name])[name]
            path = compat.patched_path(name, path, os.path.join(root, "build", "vhdl-patched"))
        files.append((lib, path))
    return analyze_files(files)
