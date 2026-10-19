"""C generation : expressions and statements of the VHDL subset used by the 63F09 design."""

import frontend
from vtypes import Bit, Enum, Int, Unsupported, Vec, const_int, type_of, unsupported
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


def mask(width):
    return "UINT64_C(0x%X)" % ((1 << width) - 1) if width < 64 else "UINT64_MAX"


class Out:
    """Indented C writer, Allman style."""

    def __init__(self):
        self.lines = []
        self.level = 0

    def line(self, text=""):
        self.lines.append(("    " * self.level + text) if text else "")

    def open(self, head):
        self.line(head)
        self.line("{")
        self.level += 1

    def close(self, tail=""):
        self.level -= 1
        self.line("}" + tail)

    def text(self):
        return "\n".join(self.lines) + "\n"


class Binding:
    """What a VHDL declaration is in the C code."""

    def __init__(self, kind, c, ct, sig=None):
        self.kind = kind        # 'sigptr' | 'sig' | 'var' | 'const' | 'local'
        self.c = c              # C expression : signal pointer, or lvalue/rvalue
        self.ct = ct
        self.sig = sig


class E:
    """A translated expression : C code and CT."""

    def __init__(self, code, ct):
        self.code = code
        self.ct = ct


class Translator:
    def __init__(self):
        self.bindings = {}
        self.out = None

    # ------------------------------------------------------------------ names and signals

    def binding(self, decl, node):
        b = self.bindings.get(decl)
        if b is None:
            raise unsupported(node, "name has no C binding (%s)" % frontend.ident(decl))
        return b

    def sigptr(self, n):
        """C expression of the vs_sig that holds the signal denoted by name node `n`, with the
        offset of the denoted part : returns (ptr, shift, width, ct)."""
        k = nodes.Get_Kind(n)
        if k in (K.Simple_Name, K.Selected_Name):
            decl = nodes.Get_Named_Entity(n)
            b = self.binding(decl, n)
            if b.kind == "sigptr":
                return b.c, 0, b.ct.width, b.ct
            if b.kind == "sig":
                return "&" + b.c, 0, b.ct.width, b.ct
            raise unsupported(n, "not a signal")
        if k in (K.Slice_Name, K.Indexed_Name):
            ptr, shift, width, ct = self.sigptr(nodes.Get_Prefix(n))
            if ct.kind != "vec":
                raise unsupported(n, "indexing a non-vector signal")
            if k == K.Slice_Name:
                lo_pos, w = self.slice_bounds(n, ct)
            else:
                lo_pos, w = self.index_pos(n, ct), 1
            if not isinstance(lo_pos, int):
                raise unsupported(n, "dynamic index on a signal target")
            return ptr, shift + lo_pos, w, (Bit() if w == 1 and k == K.Indexed_Name else Vec(w))
        raise unsupported(n, "signal name")

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
        """(bit position of the lowest bit, width) of a Slice_Name with static bounds."""
        left, right, asc = self.slice_range(n)
        lo, hi = (left, right) if asc else (right, left)
        if asc != ct.asc:
            raise unsupported(n, "slice direction differs from the vector's")
        w = hi - lo + 1
        pos_lo = (ct.hi - hi) if ct.asc else (lo - ct.lo)
        return pos_lo, w

    def slice_range(self, n):
        from vtypes import range_of
        return range_of(nodes.Get_Suffix(n))

    # ------------------------------------------------------------------ expressions

    def expr(self, n):
        k = nodes.Get_Kind(n)
        m = getattr(self, "x_" + frontend.kind_name(n), None)
        if m is None:
            raise unsupported(n, "expression")
        return m(n)

    def x_Parenthesis_Expression(self, n):
        return self.expr(nodes.Get_Expression(n))

    def x_Integer_Literal(self, n):
        return E("INT64_C(%d)" % nodes.Get_Value(n), Int())

    def x_Character_Literal(self, n):
        ch = frontend.ident(n).strip("'")      # 0, 1, U, H ...
        return E("1" if ch in ("1", "H") else "0", Bit())

    def x_Simple_Name(self, n):
        decl = nodes.Get_Named_Entity(n)
        dk = nodes.Get_Kind(decl)
        if dk == K.Enumeration_Literal:
            t = type_of(nodes.Get_Type(decl))
            return E(str(nodes.Get_Enum_Pos(decl)), t)
        b = self.binding(decl, n)
        if b.kind == "sigptr":
            return E("%s->cur" % b.c, b.ct)
        if b.kind == "sig":
            return E("%s.cur" % b.c, b.ct)
        return E(b.c, b.ct)

    x_Selected_Name = x_Simple_Name

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
        signed = type_of(nodes.Get_Type(n)).signed if type_of(nodes.Get_Type(n)).kind == "vec" else False
        width = len(bits)
        return E("UINT64_C(0x%X)" % int(bits, 2) if bits else "0", Vec(width, False, 0, width - 1, signed))

    def x_Slice_Name(self, n):
        pe = self.expr(nodes.Get_Prefix(n))
        if pe.ct.kind != "vec":
            raise unsupported(n, "slice of a non-vector")
        pos_lo, w = self.slice_bounds(n, pe.ct)
        code = "((%s >> %d) & %s)" % (pe.code, pos_lo, mask(w)) if pos_lo else "(%s & %s)" % (pe.code, mask(w))
        return E(code, Vec(w, pe.ct.asc, 0, w - 1, pe.ct.signed))

    def x_Indexed_Name(self, n):
        pe = self.expr(nodes.Get_Prefix(n))
        if pe.ct.kind != "vec":
            raise unsupported(n, "index of a non-vector")
        pos = self.index_pos(n, pe.ct)
        return E("((%s >> %s) & 1)" % (pe.code, pos), Bit())

    # operators ------------------------------------------------------------------------

    def bin2(self, n):
        return self.expr(nodes.Get_Left(n)), self.expr(nodes.Get_Right(n))

    def fit(self, e, width):
        return "(%s & %s)" % (e.code, mask(width)) if width < 64 else e.code

    def logic(self, n, op):
        a, b = self.bin2(n)
        w = max(a.ct.width, b.ct.width)
        return E("(%s %s %s)" % (a.code, op, b.code), a.ct if a.ct.width >= b.ct.width else b.ct)

    def x_And_Operator(self, n):
        return self.logic(n, "&")

    def x_Or_Operator(self, n):
        return self.logic(n, "|")

    def x_Xor_Operator(self, n):
        return self.logic(n, "^")

    def x_Not_Operator(self, n):
        a = self.expr(nodes.Get_Operand(n))
        return E("(~%s & %s)" % (a.code, mask(a.ct.width)), a.ct)

    def x_Equality_Operator(self, n):
        a, b = self.bin2(n)
        return E("(%s == %s)" % (a.code, b.code), Bit())

    def x_Inequality_Operator(self, n):
        a, b = self.bin2(n)
        return E("(%s != %s)" % (a.code, b.code), Bit())

    def x_Concatenation_Operator(self, n):
        a, b = self.bin2(n)
        if a.ct.kind not in ("bit", "vec") or b.ct.kind not in ("bit", "vec"):
            raise unsupported(n, "concatenation of these types")
        w = a.ct.width + b.ct.width
        if w > 64:
            raise unsupported(n, "concatenation wider than 64 bits")
        return E("((%s << %d) | %s)" % (a.code, b.ct.width, b.code), Vec(w))

    def x_Function_Call(self, n):
        impl = nodes.Get_Implementation(n)
        pre = nodes.Get_Implicit_Definition(impl)
        if pre in (P.Ieee_1164_Rising_Edge, P.Ieee_1164_Falling_Edge):
            arg = list(self.assoc_actuals(nodes.Get_Parameter_Association_Chain(n)))[0]
            ptr, shift, w, ct = self.sigptr(arg)
            fn = "vs_rising" if pre == P.Ieee_1164_Rising_Edge else "vs_falling"
            return E("%s(%s)" % (fn, ptr), Bit())
        raise unsupported(n, "function call (%s)" % P(pre).name)

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
            if nodes.Get_Kind(e) == K.Elsif:
                o.open("else if (%s)" % self.cond(nodes.Get_Condition(e)))
                self.stmts(nodes.Get_Sequential_Statement_Chain(e))
                o.close()
                e = nodes.Get_Else_Clause(e)
            else:
                o.open("else")
                self.stmts(nodes.Get_Sequential_Statement_Chain(e) if nodes.Get_Kind(e) == K.Elsif else e)
                o.close()
                e = 0

    def s_Null_Statement(self, s):
        self.out.line(";")

    def s_Simple_Signal_Assignment_Statement(self, s):
        wf = nodes.Get_Waveform_Chain(s)
        if not wf or nodes.Get_Chain(wf):
            raise unsupported(s, "waveform with several elements")
        if nodes.Get_Time(wf):
            raise unsupported(s, "delayed assignment")
        value = self.expr(nodes.Get_We_Value(wf))
        self.drive(nodes.Get_Target(s), value, s)

    def drive(self, target, value, s):
        ptr, shift, width, ct = self.sigptr(target)
        full = (shift == 0 and ct.width == value.ct.width) or ct.kind == "bit"
        if shift == 0 and width == self._decl_width(target):
            self.out.line("vs_drive(%s, %s);" % (ptr, value.code))
        else:
            self.out.line("vs_drive_bits(%s, %d, %s, %s);" % (ptr, shift, mask(width), value.code))

    def _decl_width(self, n):
        k = nodes.Get_Kind(n)
        if k in (K.Simple_Name, K.Selected_Name):
            return self.binding(nodes.Get_Named_Entity(n), n).ct.width
        return -1
