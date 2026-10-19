"""Generic dump of the typed tree of one design unit (debugging aid for the translator).

usage: dump.py <vhdl dir> <unit name> [depth]
"""

import os
import sys

import frontend
from pyGHDL.libghdl import name_table
from pyGHDL.libghdl.vhdl import nodes, nodes_meta

Attr = nodes_meta.Attr
Types = nodes_meta.types


def field_name(field):
    return nodes_meta.fields(field).name


def has_field(kind, field):
    first = nodes_meta.get_fields_first(kind)
    last = nodes_meta.get_fields_last(kind)
    return any(nodes_meta.get_field_by_index(i) == field for i in range(first, last + 1))


def dump(node, depth, indent=0, out=sys.stdout):
    pad = "  " * indent
    kind = nodes.Get_Kind(node)
    label = nodes.Iir_Kind(kind).name
    out.write("%s%s #%d" % (pad, label, node))
    if has_field(kind, nodes_meta.fields.Identifier):
        out.write(" '%s'" % frontend.ident(node))
    out.write("\n")
    if indent >= depth:
        return
    first = nodes_meta.get_fields_first(kind)
    last = nodes_meta.get_fields_last(kind)
    for i in range(first, last + 1):
        field = nodes_meta.get_field_by_index(i)
        ftype = nodes_meta.get_field_type(field)
        attr = nodes_meta.get_field_attribute(field)
        name = field_name(field)
        if name == "Chain":
            continue
        if ftype == Types.Iir:
            if attr in (Attr.Ref, Attr.Maybe_Ref, Attr.Forward_Ref):
                continue
            child = nodes_meta.Get_Iir(node, field)
            if child:
                out.write("%s .%s:\n" % (pad, name))
                if attr == Attr.Chain:
                    while child:
                        dump(child, depth, indent + 2, out)
                        child = nodes.Get_Chain(child)
                else:
                    dump(child, depth, indent + 2, out)
        elif ftype == Types.Boolean:
            if nodes_meta.Get_Boolean(node, field):
                out.write("%s .%s = True\n" % (pad, name))


if __name__ == "__main__":
    directory, unit_name = sys.argv[1], sys.argv[2]
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    frontend.init()
    files = frontend.find_files(directory, ["63F75"])
    for df in frontend.analyze_files([("work", files["63F75"])]):
        for unit in frontend.units(df):
            lib_unit = nodes.Get_Library_Unit(unit)
            name = frontend.ident(lib_unit)
            if name.lower() == unit_name.lower():
                dump(lib_unit, depth)
