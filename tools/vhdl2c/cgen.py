"""C generation : expressions and statements of the VHDL subset used by the 63F09 design."""

import re

import frontend
import tdefs
from cout import Out
from cops import E, Ops, W, mask, wide
from csub import Subprograms
from vtypes import Arr, Bit, Enum, Int, Rec, Unsupported, Vec, const_int, ctype_val, is_wide, numeric_kind, nwords, type_name, type_of, unsupported
from pyGHDL.libghdl.vhdl import nodes, nodes_meta

K = nodes.Iir_Kind
P = nodes.Iir_Predefined
F = nodes_meta.fields

C_KEYWORDS = set("""auto break case char const continue default do double else enum extern float for goto if
inline int long register restrict return short signed sizeof static struct switch typedef union unsigned
void volatile while main errno stdin stdout stderr abs""".split())


def cid(name):
    name = name.lower()
    return name + "_" if name in C_KEYWORDS else name


LITERAL = re.compile(r"^\(*-?(U?INT64_C\(-?(0x[0-9A-Fa-f]+|[0-9]+)\)|[0-9]+)\)*$")


class Binding:
    """What a VHDL declaration is in the C code."""

    def __init__(self, kind, c, ct, scope=None):
        self.kind = kind        # 'sigptr' | 'sig' | 'var' | 'const' | 'local'
        self.c = c              # C expression ; "{S}" stands for the structure that owns the object
        self.ct = ct
        self.scope = scope      # owner (None for the C locals)


class Translator(Subprograms, Ops):
    def __init__(self):
        self.bindings = {}
        self.out = None
        self.scope = None
        self.scope_of = {}          # AST node (architecture, generate body, block, process) -> Scope
        self.local_funcs = {}       # (decl, shape) -> FuncInst of the subprograms of the scopes

    def path_to(self, scope):
        """C expression of the structure of `scope`, seen from the code of the current scope."""
        return "self" + "->up" * (self.scope.depth - scope.depth)

    def bc(self, b):
        """C code of a binding as seen from the current scope."""
        if b.scope is None:
            return b.c
        return b.c.replace("{S}", self.path_to(b.scope))

    # ------------------------------------------------------------------ names and signals

    def binding(self, decl, node):
        b = self.bindings.get(decl)
        if b is None and nodes.Get_Kind(decl) == K.Constant_Declaration and nodes.Get_Default_Value(decl):
            # a constant of a package : its value is a constant expression
            e = self.expr(nodes.Get_Default_Value(decl))
            b = self.bindings[decl] = Binding("const", "(" + e.code + ")", type_of(nodes.Get_Type(decl)), None)
        if b is None:
            raise unsupported(node, "name has no C binding (%s)" % frontend.ident(decl))
        return b

    def path(self, n):
        """('sig' | 'var' | 'val', C code, CT) of a name : the C lvalue of the storage of a signal, the lvalue
        of a variable, or an rvalue."""
        k = nodes.Get_Kind(n)
        if k in (K.Simple_Name, K.Selected_Name):
            decl = nodes.Get_Named_Entity(n)
            if nodes.Get_Kind(decl) == K.Enumeration_Literal:
                return ("val", str(nodes.Get_Enum_Pos(decl)), type_of(nodes.Get_Type(decl)))
            b = self.binding(decl, n)
            if b.kind == "sigref":
                return ("ref", self.bc(b), b.ct)
            if b.kind == "sigptr":
                return ("sig", "(*%s)" % self.bc(b), b.ct)
            if b.kind == "sig":
                return ("sig", self.bc(b), b.ct)
            return ("var", self.bc(b), b.ct)
        if k == K.Selected_Element:
            kind, code, ct = self.path(nodes.Get_Prefix(n))
            if ct.kind != "rec":
                raise unsupported(n, "field of a non-record")
            name = frontend.ident(n).lower()
            for cname, vname, fct in ct.fields:
                if vname.lower() == name:
                    return (kind, "%s.%s" % (code, cname), fct)
            raise unsupported(n, "no field %s" % name)
        if k == K.Indexed_Name:
            kind, code, ct = self.path(nodes.Get_Prefix(n))
            if ct.kind == "arr":
                idx = list(frontend.list_elements_flist(nodes.Get_Index_List(n)))
                if len(idx) != 1:
                    raise unsupported(n, "multi-dimensional array")
                v = self.static_or_code(idx[0])
                if v is not None:
                    pos = str(ct.pos(v))
                elif ct.asc:
                    pos = "(%s) - %d" % (self.expr(idx[0]).code, ct.lo)
                else:
                    pos = "%d - (%s)" % (ct.hi, self.expr(idx[0]).code)
                return (kind, "%s.a[%s]" % (code, pos), ct.elem)
        e = self.expr(n)
        return ("val", e.code, e.ct)

    def read_path(self, kind, code, ct):
        if kind == "ref":
            return "vs_ref_get(%s)" % code
        return tdefs.get_expr(code, ct) if kind == "sig" else code

    def sigptr(self, n):
        """(pointer to the storage of the signal denoted by `n`, bit shift, width, CT) : for a part of a
        vector the pointer is that of the vector and shift and width select the part."""
        k = nodes.Get_Kind(n)
        if k in (K.Slice_Name, K.Indexed_Name):
            pk, pcode, pct = self.path(nodes.Get_Prefix(n)) if (k == K.Slice_Name or
                                                              self.prefix_is_vec(n)) else (None, None, None)
            if pct is not None and pct.kind == "vec":
                if pk != "sig":
                    raise unsupported(n, "not a signal")
                if k == K.Slice_Name:
                    lo_pos, w = self.slice_bounds(n, pct)
                    return "&" + pcode, lo_pos, w, Vec(w)
                pos = self.index_pos(n, pct)
                return "&" + pcode, pos, 1, Bit()
        kind, code, ct = self.path(n)
        if kind != "sig":
            raise unsupported(n, "not a signal")
        return "&" + code, 0, ct.width, ct

    def sigpart(self, n):
        """(storage lvalue, CT of the whole object, low bit, width) of a signal name that may be a part of a
        vector : the part is bits [low, low + width) of the object."""
        k = nodes.Get_Kind(n)
        if k in (K.Slice_Name, K.Indexed_Name) and (k == K.Slice_Name or self.prefix_is_vec(n)):
            code, bct, lo, w = self.sigpart(nodes.Get_Prefix(n))
            if bct.kind != "vec":
                raise unsupported(n, "part of a non-vector")
            if k == K.Slice_Name:
                lo_pos, ww = self.slice_bounds(n, bct)
                return code, bct, (lo + lo_pos) if isinstance(lo, int) and isinstance(lo_pos, int) else "(%s) + (%s)" % (lo, lo_pos), ww
            pos = self.index_pos(n, bct)
            if isinstance(pos, int) and isinstance(lo, int):
                return code, bct, lo + pos, 1
            # an index known only when the design is built (a generate parameter) : the bit is a C expression
            return code, bct, "(%s) + (%s)" % (lo, pos), 1
        kind, code, ct = self.path(n)
        if kind != "sig":
            raise unsupported(n, "not a signal")
        return code, ct, 0, ct.width

    def prefix_is_vec(self, n):
        pk, pcode, pct = self.path(nodes.Get_Prefix(n))
        return pct.kind == "vec"

    def static_or_code(self, expr):
        try:
            return const_int(expr)
        except Unsupported:
            return None

    def index_pos(self, n, ct):
        """Bit position of the element of an Indexed_Name : an int when static, else C code."""
        lst = nodes.Get_Index_List(n)
        elems = list(frontend.list_elements_flist(lst))
        if len(elems) != 1:
            raise unsupported(n, "multi-dimensional index")
        idx = elems[0]
        v = self.static_or_code(idx)
        if v is not None:
            return ct.pos(v)
        e = self.expr(idx)
        if ct.asc:
            return "(%d - (%s))" % (ct.hi, e.code)
        return "((%s) - %d)" % (e.code, ct.lo)

    def slice_bounds(self, n, ct):
        """(bit position of the lowest bit, width) of a Slice_Name : the width is static, the position is an int or,
        when a bound depends on a generate parameter or a loop variable, C code."""
        try:
            left, right, asc = self.slice_range(n)
        except Unsupported:
            return self.slice_bounds_dynamic(n, ct)
        lo, hi = (left, right) if asc else (right, left)
        if asc != ct.asc:
            raise unsupported(n, "slice direction differs from the vector's")
        w = hi - lo + 1
        pos_lo = (ct.hi - hi) if ct.asc else (lo - ct.lo)
        return pos_lo, w

    def slice_bounds_dynamic(self, n, ct):
        """Bounds of the form `base + c1 to base + c2` where `base` is not static."""
        rng = nodes.Get_Suffix(n)
        if nodes.Get_Kind(rng) in (K.Integer_Subtype_Definition, K.Enumeration_Subtype_Definition):
            rng = nodes.Get_Range_Constraint(rng)
        if nodes.Get_Kind(rng) != K.Range_Expression:
            raise unsupported(n, "dynamic slice range")
        asc = nodes.Get_Direction(rng) == nodes.DirectionType.To
        if asc != ct.asc:
            raise unsupported(n, "slice direction differs from the vector's")

        def split(e):
            v = self.static_or_code(e)
            if v is not None:
                return None, v
            k = nodes.Get_Kind(e)
            if k == K.Parenthesis_Expression:
                return split(nodes.Get_Expression(e))
            if k in (K.Addition_Operator, K.Substraction_Operator):
                c = self.static_or_code(nodes.Get_Right(e))
                if c is not None:
                    b, o = split(nodes.Get_Left(e))
                    return b, o + (c if k == K.Addition_Operator else -c)
            return self.expr(e).code, 0
        bl, ol = split(nodes.Get_Left_Limit_Expr(rng))
        br, orr = split(nodes.Get_Right_Limit_Expr(rng))
        if bl != br or bl is None:
            raise unsupported(n, "slice bounds that are not offsets of one expression")
        w = abs(orr - ol) + 1
        if asc:
            hi = max(ol, orr)
            return "%d - (%s) - %d" % (ct.hi, bl, hi), w
        lo = min(ol, orr)
        return "(%s) + %d - %d" % (bl, lo, ct.lo), w

    def slice_range(self, n):
        from vtypes import range_of
        return range_of(nodes.Get_Suffix(n))

    # ------------------------------------------------------------------ expressions

    def expr(self, n):
        w = self.as_written(n)
        if w != n:
            try:
                return self.expr(w)
            except Unsupported:
                pass            # what was written cannot be translated : the value will do
        k = nodes.Get_Kind(n)
        m = getattr(self, "x_" + frontend.kind_name(n), None)
        if m is None:
            raise unsupported(n, "expression")
        return m(n)

    def as_written(self, n):
        """The analyser replaces a static expression (NCPUS - 1) by its value and keeps what was written as the
        origin of the literal : the written form is translated, as it may depend on a parameter of the create
        function."""
        k = nodes.Get_Kind(n)
        if k in (K.Integer_Literal, K.Enumeration_Literal):
            if frontend.has_field(k, frontend.nodes_meta.fields.Literal_Origin):
                origin = nodes.Get_Literal_Origin(n)
                if origin:
                    return origin
        return n

    def x_Parenthesis_Expression(self, n):
        return self.expr(nodes.Get_Expression(n))

    def x_Integer_Literal(self, n):
        return E("INT64_C(%d)" % nodes.Get_Value(n), Int())

    def x_Enumeration_Literal(self, n):
        t = type_of(nodes.Get_Type(n))
        if t.kind == "bit":
            return E("1" if frontend.ident(n).strip("'") in ("1", "H", "true") else "0", Bit())
        return E(str(nodes.Get_Enum_Pos(n)), t)

    def x_Character_Literal(self, n):
        ch = frontend.ident(n).strip("'")      # 0, 1, U, H ...
        return E("1" if ch in ("1", "H") else "0", Bit())

    def x_Simple_Name(self, n):
        kind, code, ct = self.path(n)
        return E(self.read_path(kind, code, ct), ct)

    x_Selected_Name = x_Simple_Name
    x_Selected_Element = x_Simple_Name

    def x_String_Literal8(self, n):
        """A string literal holds the positions of its elements in the element's enumeration type."""
        from pyGHDL.libghdl import str_table
        from vtypes import base_of
        length = nodes.Get_String_Length(n)
        raw = str_table.Get_String8_Ptr(nodes.Get_String8_Id(n), length)
        arr = base_of(nodes.Get_Type(n))
        elem = base_of(nodes.Get_Element_Subtype(arr))
        names = [frontend.ident(l).strip("'") for l in frontend.list_elements_flist(nodes.Get_Enumeration_Literal_List(elem))]
        bits = "".join("1" if names[ord(c)] in ("1", "H") else "0" for c in raw)
        signed = numeric_kind(arr) == "signed"
        width = len(bits)
        if width > 64:
            v = int(bits, 2)
            words = ["UINT64_C(0x%X)" % ((v >> (64 * i)) & ((1 << 64) - 1)) for i in range((width + 63) // 64)]
            return E("((vs_w){{%s}})" % ", ".join(words), Vec(width, False, 0, width - 1, signed))
        return E("UINT64_C(0x%X)" % int(bits, 2) if bits else "0", Vec(width, False, 0, width - 1, signed))

    def x_Slice_Name(self, n):
        pe = self.expr(nodes.Get_Prefix(n))
        if pe.ct.kind != "vec":
            raise unsupported(n, "slice of a non-vector")
        pos_lo, w = self.slice_bounds(n, pe.ct)
        if wide(pe):
            code = "vs_w_slice(%s, %s, %d)" % (pe.code, pos_lo, w)
            return E(code if w > 64 else "vs_w_u64(%s)" % code, Vec(w, pe.ct.asc, 0, w - 1, pe.ct.signed))
        code = "((%s >> (%s)) & %s)" % (pe.code, pos_lo, mask(w)) if pos_lo != 0 else "(%s & %s)" % (pe.code, mask(w))
        return E(code, Vec(w, pe.ct.asc, 0, w - 1, pe.ct.signed))

    def x_Indexed_Name(self, n):
        if not self.prefix_is_vec(n):
            kind, code, ct = self.path(n)
            return E(self.read_path(kind, code, ct), ct)
        pe = self.expr(nodes.Get_Prefix(n))
        pos = self.index_pos(n, pe.ct)
        if wide(pe):
            return E("vs_w_bit(%s, %s)" % (pe.code, pos), Bit())
        return E("((%s >> %s) & 1)" % (pe.code, pos), Bit())

    def assoc_actuals(self, chain):
        a = chain
        while a:
            yield nodes.Get_Actual(a)
            a = nodes.Get_Chain(a)

    # ------------------------------------------------------------------ statements

    def stmts(self, chain):
        s = chain
        while s:
            self.stmt(s)
            s = nodes.Get_Chain(s)

    def stmt(self, s):
        k = nodes.Get_Kind(s)
        m = getattr(self, "s_" + frontend.kind_name(s), None)
        if m is None:
            raise unsupported(s, "statement")
        m(s)

    def cond(self, c):
        e = self.expr(c)
        return e.code

    def s_If_Statement(self, s):
        o = self.out
        o.open("if (%s)" % self.cond(nodes.Get_Condition(s)))
        self.stmts(nodes.Get_Sequential_Statement_Chain(s))
        o.close()
        e = nodes.Get_Else_Clause(s)
        while e:
            c = nodes.Get_Condition(e)
            if c:
                o.open("else if (%s)" % self.cond(c))
            else:
                o.open("else")
            self.stmts(nodes.Get_Sequential_Statement_Chain(e))
            o.close()
            e = nodes.Get_Else_Clause(e)

    def s_Null_Statement(self, s):
        self.out.line(";")

    # ------------------------------------------------------------------ assignments

    def target_lvalue(self, target):
        """(kind, base C code, shift, mask, width, CT, base CT) of a target name : kind is 'sig' (base is the
        storage lvalue) or 'var' (base is the variable lvalue) ; shift and mask select the part of a vector."""
        k = nodes.Get_Kind(target)
        if k in (K.Slice_Name, K.Indexed_Name) and (k == K.Slice_Name or self.prefix_is_vec(target)):
            kind, base, shift, m, width, ct, bct = self.target_lvalue(nodes.Get_Prefix(target))
            if ct.kind != "vec":
                raise unsupported(target, "indexing a non-vector target")
            if k == K.Slice_Name:
                lo_pos, w = self.slice_bounds(target, ct)
                return (kind, base, lo_pos, mask(w) if w < 64 else "UINT64_MAX", w, Vec(w), bct)
            pos = self.index_pos(target, ct)
            if isinstance(pos, int):
                return (kind, base, pos, mask(1), 1, Bit(), bct)
            return (kind, base, pos, "(UINT64_C(1))", 1, Bit(), bct)
        kind, code, ct = self.path(target)
        if kind == "val":
            raise unsupported(target, "assignment target")
        return (kind, code, 0, mask(ct.width) if ct.width and ct.width <= 64 else "0", ct.width, ct, ct)

    def assign(self, target, value, scope_kind):
        kind, base, shift, m, width, ct, bct = self.target_lvalue(target)
        o = self.out
        v = value.code
        if kind == "ref":
            if isinstance(shift, int) and shift == 0 and ct.width == bct.width:
                o.line("vs_ref_drive(%s, (uint64_t)(%s));" % (base, v))
            else:
                o.line("vs_ref_drive_bits(%s, %s, %s, (uint64_t)(%s));" % (base, shift, m, v))
            return
        if ct.kind in ("rec", "arr"):
            o.line(tdefs.drive_stmt(base, ct, v) if kind == "sig" else "%s = %s;" % (base, v))
            return
        if is_wide(bct):
            nw = nwords(bct)
            whole = is_wide(ct)
            if kind == "sig":
                if whole:
                    o.line("vs_w_drive(%s.w, %d, %s);" % (base, nw, W(value)))
                else:
                    o.line("vs_w_drive_bits(%s.w, %d, %s, %d, %s);" % (base, nw, shift, width, W(value)))
            else:
                if whole:
                    o.line("%s = %s;" % (base, W(value)))
                else:
                    o.line("%s = vs_w_set(%s, %s, %d, %s);" % (base, base, shift, width, W(value)))
            return
        whole = isinstance(shift, int) and shift == 0 and (ct.width == self.object_width(target))
        if ct.kind == "int" or value.ct.kind == "int":
            v = "(uint64_t)(%s)" % v if kind == "sig" else v
        if kind == "sig":
            if whole:
                o.line("vs_drive(&%s, %s);" % (base, v))
            else:
                o.line("vs_drive_bits(&%s, %s, %s, %s);" % (base, shift, m, v))
        else:
            if whole:
                o.line("%s = %s;" % (base, v))
            else:
                o.line("%s = (%s & ~(%s << %s)) | ((%s << %s) & (%s << %s));" % (base, base, m, shift, v, shift, m, shift))

    def object_width(self, target):
        """Width of the whole object a target denotes (-1 when the target is a part of a vector)."""
        k = nodes.Get_Kind(target)
        if k in (K.Slice_Name,) or (k == K.Indexed_Name and self.prefix_is_vec(target)):
            return -1
        return self.path(target)[2].width

    def expr_as(self, node, ct):
        """The expression translated for an object of the given type (the elements of an aggregate)."""
        saved = (getattr(self, "want", None), getattr(self, "want_node", None))
        self.want, self.want_node = ct, node
        try:
            return self.expr(node)
        finally:
            self.want, self.want_node = saved

    def expr_to(self, node, target):
        """The expression translated for assignment to `target` : an aggregate takes its shape from the target
        when it has no bounds of its own."""
        saved = (getattr(self, "want", None), getattr(self, "want_node", None))
        self.want = self.target_lvalue(target)[5]
        self.want_node = node
        try:
            return self.expr(node)
        finally:
            self.want, self.want_node = saved

    def s_Simple_Signal_Assignment_Statement(self, s):
        wf = nodes.Get_Waveform_Chain(s)
        if not wf or nodes.Get_Chain(wf):
            raise unsupported(s, "waveform with several elements")
        if nodes.Get_Time(wf):
            raise unsupported(s, "delayed assignment")
        self.assign(nodes.Get_Target(s), self.expr_to(nodes.Get_We_Value(wf), nodes.Get_Target(s)), "sig")

    def s_Variable_Assignment_Statement(self, s):
        self.assign(nodes.Get_Target(s), self.expr_to(nodes.Get_Expression(s), nodes.Get_Target(s)), "var")

    def s_Conditional_Signal_Assignment_Statement(self, s):
        self.conditional(s, nodes.Get_Target(s), nodes.Get_Conditional_Waveform_Chain(s))

    def conditional(self, s, target, chain):
        """target <= a when c1 else b when c2 else d : an if / else if / else chain."""
        o = self.out
        first = True
        w = chain
        while w:
            cond = nodes.Get_Condition(w)
            wf = nodes.Get_Waveform_Chain(w)
            if not wf or nodes.Get_Chain(wf):
                raise unsupported(w, "waveform with several elements")
            if cond:
                o.open("%sif (%s)" % ("" if first else "else ", self.cond(cond)))
            else:
                o.open("else")
            self.assign(target, self.expr_to(nodes.Get_We_Value(wf), target), "sig")
            o.close()
            first = False
            w = nodes.Get_Chain(w)

    def s_Selected_Waveform_Assignment_Statement(self, s):
        self.selected(s, nodes.Get_Target(s), nodes.Get_Expression(s), nodes.Get_Selected_Waveform_Chain(s))

    def selected(self, s, target, selector, chain):
        """with sel select target <= a when "00", b when others : a switch."""
        o = self.out
        sel = self.expr(selector)
        o.open("switch (%s)" % sel.code)
        w = chain
        while w:
            ch = nodes.Get_Choice_Kind_Placeholder(w) if False else w
            self.case_labels(w)
            wf = nodes.Get_Associated_Chain(w)
            while w and True:
                nxt = nodes.Get_Chain(w)
                if nxt and nodes.Get_Same_Alternative_Flag(nxt):
                    w = nxt
                    self.case_labels(w)
                else:
                    break
            o.line("{")
            o.level += 1
            if not wf or nodes.Get_Chain(wf):
                raise unsupported(w, "waveform with several elements")
            self.assign(target, self.expr_to(nodes.Get_We_Value(wf), target), "sig")
            o.line("break;")
            o.level -= 1
            o.line("}")
            w = nodes.Get_Chain(w)
        o.close()

    # ------------------------------------------------------------------ case

    def case_labels(self, choice):
        o = self.out
        k = nodes.Get_Kind(choice)
        if k == K.Choice_By_Others:
            o.line("default:")
        elif k == K.Choice_By_Expression:
            o.line("case %s:" % self.expr(nodes.Get_Choice_Expression(choice)).code)
        elif k == K.Choice_By_Range:
            from vtypes import range_of
            left, right, asc = range_of(nodes.Get_Choice_Range(choice))
            lo, hi = (left, right) if asc else (right, left)
            if hi - lo > 255:
                raise unsupported(choice, "wide choice range")
            for v in range(lo, hi + 1):
                o.line("case %d:" % v)
        else:
            raise unsupported(choice, "choice")

    def matching_test(self, sel, choice):
        """Condition of a choice of a `case?` : '-' in the choice matches any bit of the selector."""
        from pyGHDL.libghdl import str_table
        k = nodes.Get_Kind(choice)
        if k == K.Choice_By_Others:
            return "1"
        if k != K.Choice_By_Expression:
            raise unsupported(choice, "choice of a matching case")
        e = nodes.Get_Choice_Expression(choice)
        while nodes.Get_Kind(e) == K.Parenthesis_Expression:
            e = nodes.Get_Expression(e)
        if nodes.Get_Kind(e) != K.String_Literal8 or wide(sel):
            return "%s == %s" % (sel.code, self.expr(e).code)
        from vtypes import base_of
        arr = base_of(nodes.Get_Type(e))
        elem = base_of(nodes.Get_Element_Subtype(arr))
        names = [frontend.ident(l).strip("'") for l in frontend.list_elements_flist(nodes.Get_Enumeration_Literal_List(elem))]
        raw = "".join(names[ord(c)] for c in str_table.Get_String8_Ptr(nodes.Get_String8_Id(e), nodes.Get_String_Length(e)))
        m = int("".join("0" if c == "-" else "1" for c in raw), 2)
        v = int("".join("1" if c in "1H" else "0" for c in raw), 2)
        if any(c in "UXWZ" for c in raw):
            return "0"
        return "(%s & UINT64_C(0x%X)) == UINT64_C(0x%X)" % (sel.code, m, v)

    def s_Case_Matching(self, s):
        o = self.out
        sel = self.expr(nodes.Get_Expression(s))
        first = True
        choice = nodes.Get_Case_Statement_Alternative_Chain(s)
        others = None
        while choice:
            tests = [self.matching_test(sel, choice)]
            stmts = nodes.Get_Associated_Chain(choice)
            nxt = nodes.Get_Chain(choice)
            while nxt and nodes.Get_Same_Alternative_Flag(nxt):
                choice = nxt
                tests.append(self.matching_test(sel, choice))
                nxt = nodes.Get_Chain(choice)
            if "1" in tests:
                others = stmts
            else:
                o.open("%sif (%s)" % ("" if first else "else ", " || ".join("(%s)" % t for t in tests)))
                self.stmts(stmts)
                o.close()
                first = False
            choice = nxt
        if others is not None:
            if first:
                o.open("")
            else:
                o.open("else")
            self.stmts(others)
            o.close()

    def s_Case_Statement(self, s):
        if nodes.Get_Matching_Flag(s):
            return self.s_Case_Matching(s)
        o = self.out
        sel = self.expr(nodes.Get_Expression(s))
        o.open("switch (%s)" % sel.code)
        choice = nodes.Get_Case_Statement_Alternative_Chain(s)
        while choice:
            self.case_labels(choice)
            stmts = nodes.Get_Associated_Chain(choice)
            nxt = nodes.Get_Chain(choice)
            while nxt and nodes.Get_Same_Alternative_Flag(nxt):
                choice = nxt
                self.case_labels(choice)
                nxt = nodes.Get_Chain(choice)
            o.line("{")
            o.level += 1
            self.stmts(stmts)
            o.line("break;")
            o.level -= 1
            o.line("}")
            choice = nxt
        o.close()

    # ------------------------------------------------------------------ loops

    def new_label(self):
        self.label_count = getattr(self, "label_count", 0) + 1
        return self.label_count

    def s_For_Loop_Statement(self, s):
        o = self.out
        spec = nodes.Get_Parameter_Specification(s)
        left, right, asc = self.loop_range(spec)
        name = "i_%d" % self.new_label()
        self.bindings[spec] = Binding("local", name, Int())
        lid = self.new_label()
        self.loops = getattr(self, "loops", []) + [(s, lid)]
        if asc:
            o.open("for (int64_t %s = %s; %s <= %s; %s++)" % (name, left, name, right, name))
        else:
            o.open("for (int64_t %s = %s; %s >= %s; %s--)" % (name, left, name, right, name))
        start = len(o.lines)
        self.stmts(nodes.Get_Sequential_Statement_Chain(s))
        self.loop_labels(o, start, lid)
        o.close()
        if self.label_used(o, start, "loop_exit_%d" % lid):
            o.line("loop_exit_%d:;" % lid)
        self.loops.pop()

    def s_While_Loop_Statement(self, s):
        o = self.out
        lid = self.new_label()
        self.loops = getattr(self, "loops", []) + [(s, lid)]
        c = nodes.Get_Condition(s)
        o.open("while (%s)" % (self.cond(c) if c else "1"))
        start = len(o.lines)
        self.stmts(nodes.Get_Sequential_Statement_Chain(s))
        self.loop_labels(o, start, lid)
        o.close()
        if self.label_used(o, start, "loop_exit_%d" % lid):
            o.line("loop_exit_%d:;" % lid)
        self.loops.pop()

    def label_used(self, o, start, label):
        return any("goto %s;" % label in line for line in o.lines[start:])

    def loop_labels(self, o, start, lid):
        """The label that ends the body of a loop, when a next statement jumps to it."""
        if self.label_used(o, start, "loop_next_%d" % lid):
            o.line("loop_next_%d:;" % lid)

    def loop_range(self, rng):
        """(left C code, right C code, ascending) of the discrete range of a loop ; `rng` is the Iterator_Declaration
        (the range is its Discrete_Range or, when that is empty, its subtype indication) or the range itself."""
        if nodes.Get_Kind(rng) == K.Iterator_Declaration:
            r = nodes.Get_Discrete_Range(rng)
            rng = r if r else nodes.Get_Subtype_Indication(rng)
        k = nodes.Get_Kind(rng)
        if k in (K.Integer_Subtype_Definition, K.Enumeration_Subtype_Definition):
            inner = nodes.Get_Range_Constraint(rng)
            if inner:
                rng = inner
                k = nodes.Get_Kind(rng)
        if k == K.Range_Expression:
            asc = nodes.Get_Direction(rng) == nodes.DirectionType.To
            le, re_ = nodes.Get_Left_Limit_Expr(rng), nodes.Get_Right_Limit_Expr(rng)
            if not le:
                raise unsupported(rng, "loop range without explicit limits")
            return (self.expr(le).code, self.expr(re_).code, asc)
        if k in (K.Range_Array_Attribute, K.Reverse_Range_Array_Attribute):
            ct = self.expr(nodes.Get_Prefix(rng)).ct
            if ct.kind == "vec" and ct.width is not None:
                lo, hi, asc = ct.lo, ct.hi, ct.asc
            elif ct.kind == "arr":
                lo, hi, asc = ct.lo, ct.hi, ct.asc
            else:
                raise unsupported(rng, "'range of this prefix")
            first, last = (lo, hi) if asc else (hi, lo)
            if k == K.Reverse_Range_Array_Attribute:
                first, last, asc = last, first, not asc
            return (str(first), str(last), asc)
        raise unsupported(rng, "loop range")

    def loop_target(self, s):
        label = nodes.Get_Loop_Label(s) if frontend.has_field(nodes.Get_Kind(s), F.Loop_Label) else 0
        if label:
            decl = nodes.Get_Named_Entity(label) if nodes.Get_Kind(label) in (K.Simple_Name,) else label
            for st, lid in reversed(self.loops):
                if st == decl or nodes.Get_Label(st) == nodes.Get_Identifier(decl):
                    return lid
        return self.loops[-1][1]

    def s_Exit_Statement(self, s):
        lid = self.loop_target(s)
        c = nodes.Get_Condition(s)
        self.out.line(("if (%s) " % self.cond(c) if c else "") + "goto loop_exit_%d;" % lid)

    def s_Next_Statement(self, s):
        lid = self.loop_target(s)
        c = nodes.Get_Condition(s)
        self.out.line(("if (%s) " % self.cond(c) if c else "") + "goto loop_next_%d;" % lid)

    def s_Report_Statement(self, s):
        self.out.line("/* report */")

    def s_Assertion_Statement(self, s):
        self.out.line("/* assert */")

    # ------------------------------------------------------------------ aggregates and attributes

    def aggregate_items(self, n):
        """[(kind, value, expr)] of an aggregate : kind is 'others', 'pos', 'index' (value = index), 'range'
        (value = (lo, hi)) or 'field' (value = field name) ; expr is the associated expression node."""
        from vtypes import range_of
        items = []
        if nodes.Get_Kind(n) == K.Simple_Aggregate:
            for e in frontend.list_elements_flist(nodes.Get_Simple_Aggregate_List(n)):
                items.append(("pos", None, e))
            return items
        ch = nodes.Get_Association_Choices_Chain(n)
        cur = 0
        while ch:
            ck = nodes.Get_Kind(ch)
            if not nodes.Get_Same_Alternative_Flag(ch):
                cur = nodes.Get_Associated_Expr(ch)
            if ck == K.Choice_By_Others:
                items.append(("others", None, cur))
            elif ck == K.Choice_By_None:
                items.append(("pos", None, cur))
            elif ck == K.Choice_By_Expression:
                items.append(("index", self.static_index(nodes.Get_Choice_Expression(ch), n), cur))
            elif ck == K.Choice_By_Range:
                left, right, asc = range_of(nodes.Get_Choice_Range(ch))
                if (left > right) if asc else (left < right):
                    pass        # a null range (NCPUS - 2 with one core) chooses nothing
                else:
                    items.append(("range", (min(left, right), max(left, right)), cur))
            elif ck == K.Choice_By_Name:
                nm = nodes.Get_Choice_Name(ch)
                items.append(("field", frontend.ident(nodes.Get_Named_Entity(nm)).lower(), cur))
            else:
                raise unsupported(ch, "aggregate choice")
            ch = nodes.Get_Chain(ch)
        return items

    def aggregate_type(self, n, items):
        """CT of an aggregate : its own subtype, or the one it is assigned to when it has no bounds."""
        try:
            t = type_of(nodes.Get_Type(n))
            if not (t.kind == "vec" and t.width is None):
                return t
        except Unsupported:
            t = None
        want = getattr(self, "want", None)
        root = getattr(self, "want_node", None)
        while root and nodes.Get_Kind(root) == K.Parenthesis_Expression:
            root = nodes.Get_Expression(root)
        if root == n and want is not None and want.kind in ("vec", "rec", "arr") and not (want.kind == "vec" and want.width is None):
            return want
        if items and all(kind == "pos" for kind, v, e in items):
            return Vec(len(items), False, 0, len(items) - 1, False)
        if items and all(kind == "range" for kind, v, e in items):
            lo = min(v[0] for kind, v, e in items)
            hi = max(v[1] for kind, v, e in items)
            from vtypes import range_of
            ch = nodes.Get_Association_Choices_Chain(n)
            asc = range_of(nodes.Get_Choice_Range(ch))[2]
            return Vec(hi - lo + 1, asc, lo, hi, False)
        raise unsupported(n, "aggregate whose shape cannot be determined")

    def x_Aggregate(self, n):
        items = self.aggregate_items(n)
        t = self.aggregate_type(n, items)
        if t.kind == "rec":
            code = "%s_zero()" % t.cname
            named = set()
            pos = 0
            for kind, val, expr in items:
                if kind == "pos":
                    fname = t.fields[pos][0]
                    pos += 1
                elif kind == "field":
                    fname = next(f[0] for f in t.fields if f[1].lower() == val)
                else:
                    continue
                named.add(fname)
                fct = next(f[2] for f in t.fields if f[0] == fname)
                code = "%s_with_%s(%s, %s)" % (t.cname, fname, code, self.expr_as(expr, fct).code)
            for kind, val, expr in items:
                if kind == "others":
                    for fname, vname, fct in t.fields:
                        if fname not in named:
                            code = "%s_with_%s(%s, %s)" % (t.cname, fname, code, self.expr_as(expr, fct).code)
            return E(code, t)
        if t.kind == "arr":
            code = None
            literal = True          # every element is a literal : the aggregate is a constant
            for kind, val, expr in items:
                if kind == "others":
                    e = self.expr_as(expr, t.elem).code
                    literal = literal and bool(LITERAL.match(e))
                    code = "%s_fill(%s)" % (t.cname, e)
            if code is None:
                code = "%s_zero()" % t.cname
            pos = 0
            for kind, val, expr in items:
                if kind == "pos":
                    e = self.expr_as(expr, t.elem).code
                    code = "%s_put(%s, %d, %s)" % (t.cname, code, pos, e)
                    pos += 1
                elif kind == "index":
                    e = self.expr_as(expr, t.elem).code
                    code = "%s_put(%s, %d, %s)" % (t.cname, code, t.pos(val), e)
                elif kind == "range":
                    e = self.expr_as(expr, t.elem).code
                    for i in range(val[0], val[1] + 1):
                        code = "%s_put(%s, %d, %s)" % (t.cname, code, t.pos(i), e)
                else:
                    continue
                literal = literal and bool(LITERAL.match(e))
            if literal and len(items) > 8:
                return E("(*%s())" % tdefs.hoist(t.cname, code), t)
            return E(code, t)
        if t.kind not in ("vec", "bit"):
            raise unsupported(n, "aggregate of this type")
        w = t.width
        if w is None:
            raise unsupported(n, "aggregate of unconstrained vector")
        # The bits that are constants are folded ; the others are set one by one.
        value = 0
        dyn = []            # (bit position, count, expression)
        fill = None
        for kind, val, expr in items:
            if kind == "others":
                fill = self.expr(expr)
        covered = set()
        pos = 0
        for kind, val, expr in items:
            if kind == "others":
                continue
            e = self.expr(expr)
            if kind == "pos":
                lo, cnt = w - 1 - pos, 1
                pos += 1
            elif kind == "index":
                lo, cnt = t.pos(val), 1
            else:
                lo = t.pos(val[0]) if not t.asc else t.pos(val[1])
                cnt = val[1] - val[0] + 1
            for bit in range(lo, lo + cnt):
                covered.add(bit)
            if e.code in ("0", "1"):
                if e.code == "1":
                    value |= ((1 << cnt) - 1) << lo
            else:
                dyn.append((lo, cnt, e))
        if fill is not None:
            if fill.code in ("0", "1"):
                if fill.code == "1":
                    for bit in range(w):
                        if bit not in covered:
                            value |= 1 << bit
            else:
                runs = []
                for bit in range(w):
                    if bit not in covered:
                        if runs and runs[-1][0] + runs[-1][1] == bit:
                            runs[-1][1] += 1
                        else:
                            runs.append([bit, 1])
                for lo, cnt in runs:
                    dyn.append((lo, cnt, fill))
        if w > 64:
            words = ["UINT64_C(0x%X)" % ((value >> (64 * i)) & ((1 << 64) - 1)) for i in range((w + 63) // 64)]
            code = "((vs_w){{%s}})" % ", ".join(words)
            for lo, cnt, e in dyn:
                if cnt <= 0:
                    continue
                code = "vs_w_set(%s, %d, %d, %s)" % (code, lo, cnt, ("(%s ? vs_w_ones(%d) : vs_w_zero())" % (e.code, cnt)) if cnt > 1 or e.ct.kind == "bit" and cnt > 1 else W(e))
            return E(code, t)
        code = "UINT64_C(0x%X)" % value
        for lo, cnt, e in dyn:
            if cnt <= 0:
                continue
            if lo < 0:
                raise unsupported(n, 'aggregate bit position %d (count %d, width %d)' % (lo, cnt, w))
            m = ((1 << cnt) - 1) << lo
            if cnt == 1:
                code = "((%s & ~UINT64_C(0x%X)) | ((%s & 1) << %d))" % (code, m, e.code, lo)
            else:
                code = "((%s & ~UINT64_C(0x%X)) | (%s ? UINT64_C(0x%X) : 0))" % (code, m, e.code, m)
        return E(code, Vec(w, t.asc, t.lo, t.hi, t.signed) if t.kind == "vec" else t)

    x_Simple_Aggregate = x_Aggregate

    def static_index(self, expr, n):
        from vtypes import const_int
        return const_int(expr)

    def x_Qualified_Expression(self, n):
        return self.expr(nodes.Get_Expression(n))

    def x_Type_Conversion(self, n):
        e = self.expr(nodes.Get_Expression(n))
        t = type_of(nodes.Get_Type(n))
        if t.kind == "vec" and e.ct.kind == "vec":
            w = t.width if t.width is not None else e.ct.width
            return E(e.code, Vec(w, e.ct.asc, e.ct.lo, e.ct.hi, t.signed))
        if t.kind == "int" and e.ct.kind in ("int", "vec"):
            return E(e.code if e.ct.kind == "int" else "(int64_t)(%s)" % e.code, Int())
        if t.kind == e.ct.kind:
            return e
        raise unsupported(n, "type conversion")

    def x_Length_Array_Attribute(self, n):
        e = self.expr(nodes.Get_Prefix(n))
        if e.ct.kind == "bit":
            return E("1", Int())
        if e.ct.kind != "vec" or e.ct.width is None:
            raise unsupported(n, "'length of this prefix")
        return E("INT64_C(%d)" % e.ct.width, Int())

    def x_Event_Attribute(self, n):
        ptr, shift, w, ct = self.sigptr(nodes.Get_Prefix(n))
        return E("(%s)->evt" % ptr, Bit())

    def x_High_Type_Attribute(self, n):
        raise unsupported(n, "'high of a type")

    def x_Parenthesis_Expression(self, n):
        return self.expr(nodes.Get_Expression(n))

    def s_Procedure_Call_Statement(self, s):
        call = nodes.Get_Procedure_Call(s)
        impl = nodes.Get_Implementation(call)
        if frontend.ident(impl) == "finish":
            self.out.line("vs_finished = 1;")
            return
        self.user_procedure_call(s, call)


def need_w(n, w):
    if w is None or w > 64:
        raise unsupported(n, "vector wider than 64 bits")
    return w


def ct_width_of(tr, n):
    """Width of the object a target name denotes as a whole (-1 when it is part of one)."""
    k = nodes.Get_Kind(n)
    if k in (K.Simple_Name, K.Selected_Name):
        return tr.binding(nodes.Get_Named_Entity(n), n).ct.width
    return -1
