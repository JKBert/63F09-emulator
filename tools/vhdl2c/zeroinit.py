"""Test-only rewrite of the VHDL sources : the registers start at 0, like the flip-flops of the FPGA.

VHDL gives 'U' to a std_logic that has no initial value, and 'U' is not equal to anything : a register
that the design never resets (a divider that is written before use, say) makes GHDL and the C model
disagree during the first cycles although the hardware is perfectly defined (every flip-flop of the
FPGA is loaded with 0 when the device is configured). The test copies of the sources therefore get an
explicit initial value on every signal, variable and entity port of the std_logic family that has none.

The generator never sees these copies.
"""

import os

import frontend
from vtypes import SUBTYPE_KINDS, Unsupported, base_of, const_int, range_of, type_name
from pyGHDL.libghdl import files_map, name_table
from pyGHDL.libghdl.vhdl import nodes

K = nodes.Iir_Kind
BITLIKE = ("std_ulogic",)


def default_text(t):
    """VHDL text of a 'zero' value of the type, or None when the type has no std_logic in it."""
    b = base_of(t)
    k = nodes.Get_Kind(b)
    if k == K.Enumeration_Type_Definition:
        return "'0'" if type_name(b) in BITLIKE else None
    if k == K.Array_Type_Definition:
        elem = default_text(nodes.Get_Element_Subtype(b))
        return "(others => %s)" % elem if elem else None
    return None


def end_of_declaration(text, pos):
    """Offset of the ';' (or of the ')' that closes a port list) that ends the declaration at pos."""
    depth = 0
    i = pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "-" and text[i:i + 2] == "--":
            i = text.find("\n", i)
            if i < 0:
                return None
            continue
        if c == "/" and text[i:i + 2] == "/*":
            i = text.find("*/", i) + 2
            continue
        if c == '"':
            i = text.find('"', i + 1) + 1
            continue
        if c == "'" and i + 2 < n and text[i + 2] == "'":
            i += 3
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                return i
            depth -= 1
        elif c == ";" and depth == 0:
            return i
        i += 1
    return None


def declarations(unit):
    for n in frontend.walk(unit):
        k = nodes.Get_Kind(n)
        if k in (K.Signal_Declaration, K.Variable_Declaration):
            if not nodes.Get_Default_Value(n):
                yield n
        elif k == K.Interface_Signal_Declaration:
            parent = nodes.Get_Parent(n)
            if parent and nodes.Get_Kind(parent) in (K.Entity_Declaration, K.Component_Declaration):
                if not nodes.Get_Default_Value(n):
                    yield n


def patch(design_files, files, out_dir):
    """Writes patched copies of the files (skipping the library of the Xilinx primitives) and
    returns the new (library, path) list."""
    os.makedirs(out_dir, exist_ok=True)
    edits = {}          # path -> {offset: text}
    for df, (lib, path) in zip(design_files, files):
        if lib == "unisim":
            continue
        for unit in frontend.units(df):
            for d in declarations(unit):
                text = default_text(nodes.Get_Type(d))
                if text is None:
                    continue
                loc = nodes.Get_Location(d)
                fe = files_map.Location_To_File(loc)
                fpath = os.path.join(name_table.Get_Name_Ptr(files_map.Get_Directory_Name(fe)),
                                     name_table.Get_Name_Ptr(files_map.Get_File_Name(fe)))
                src = open(fpath, encoding="utf-8", errors="replace").read()
                pos = files_map.Location_File_To_Pos(loc, fe)
                end = end_of_declaration(src, pos)
                if end is None:
                    continue
                edits.setdefault(fpath, {})[end] = " := " + text
    result = []
    for df, (lib, path) in zip(design_files, files):
        if path in edits:
            src = open(path, encoding="utf-8", errors="replace").read()
            for off in sorted(edits[path], reverse=True):
                src = src[:off] + edits[path][off] + src[off:]
            dest = os.path.join(out_dir, os.path.basename(path))
            open(dest, "w", encoding="utf-8").write(src)
            result.append((lib, dest))
        else:
            result.append((lib, path))
    return result
