"""Dump of the typed tree of one design unit (debugging aid for the translator).

usage: dump.py <vhdl dir> <unit name> [depth]

Names, literal values and the type of each expression are shown ; references to declarations
are shown by name and are not followed.
"""

import os
import sys

import frontend
from pyGHDL.libghdl import name_table
from pyGHDL.libghdl.vhdl import nodes, nodes_meta

F = nodes_meta.fields


def label(node):
    kind = nodes.Get_Kind(node)
    out = "%s #%d" % (nodes.Iir_Kind(kind).name, node)
    for field in frontend.fields_of(kind):
        if field == F.Identifier:
            out += " '%s'" % frontend.ident(node)
        elif field == F.Literal_Origin and False:
            pass
    name = nodes.Iir_Kind(kind).name
    if name == "Integer_Literal":
        out += " = %d" % nodes.Get_Value(node)
    if name in ("Simple_Name", "Selected_Name", "Character_Literal"):
        out += " '%s'" % frontend.ident(node)
        ent = nodes.Get_Named_Entity(node) if name != "Character_Literal" else 0
        if ent:
            out += " -> %s #%d" % (frontend.kind_name(ent), ent)
    for field in frontend.fields_of(kind):
        if field == F.Type:
            t = nodes.Get_Type(node)
            if t:
                out += " : type %s #%d" % (frontend.kind_name(t), t)
                tdecl = nodes.Get_Type_Declarator(t) if frontend.has_field(nodes.Get_Kind(t), F.Type_Declarator) else 0
                if tdecl:
                    out += " (%s)" % frontend.ident(tdecl)
    return out


def dump(node, depth, indent=0, out=sys.stdout):
    pad = "  " * indent
    out.write(pad + label(node) + "\n")
    if indent >= depth:
        return
    for field, child in frontend.children(node):
        fname = F(field).name
        if fname == "Chain":
            continue
        out.write("%s .%s\n" % (pad, fname))
        dump(child, depth, indent + 2, out)


if __name__ == "__main__":
    directory, unit_name = sys.argv[1], sys.argv[2]
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    frontend.init()
    here = os.path.dirname(os.path.abspath(__file__))
    for df in frontend.load_project(directory, os.path.join(here, "sources.list")):
        for unit in frontend.units(df):
            lib_unit = nodes.Get_Library_Unit(unit)
            if frontend.ident(lib_unit).lower() == unit_name.lower():
                dump(lib_unit, depth)
