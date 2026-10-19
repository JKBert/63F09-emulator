"""C generation : expressions and statements of the VHDL subset used by the 63F09 design."""

import frontend
from cops import E, Ops, mask
from vtypes import Bit, Enum, Int, Unsupported, Vec, const_int, type_name, type_of, unsupported
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

    def __init__(self, kind, c, ct, scope=None):
        self.kind = kind        # 'sigptr' | 'sig' | 'var' | 'const' | 'local'
        self.c = c              # C expression ; "{S}" stands for the structure that owns the object
        self.ct = ct
        self.scope = scope      # owner (None for the C locals)


class Translator(Ops):
    def __init__(self):
        self.bindings = {}
        self.out = None
        self.scope = None

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
                return self.bc(b), 0, b.ct.width, b.ct
            if b.kind == "sig":
                return "&" + self.bc(b), 0, b.ct.width, b.ct
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
            return E("%s->cur" % self.bc(b), b.ct)
        if b.kind == "sig":
            return E("%s.cur" % self.bc(b), b.ct)
        return E(self.bc(b), b.ct)

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
        signed = type_name(arr) == "signed"
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

    def s_Simple_Signal_Assignment_Statement(self, s):
        wf = nodes.Get_Waveform_Chain(s)
        if not wf or nodes.Get_Chain(wf):
            raise unsupported(s, "waveform with several elements")
        if nodes.Get_Time(wf):
            raise unsupported(s, "delayed assignment")
        value = self.expr(nodes.Get_We_Value(wf))
        self.drive(nodes.Get_Target(s), value, s)

    # ------------------------------------------------------------------ assignments

    def target_lvalue(self, target):
        """('sig', ptr, shift, mask, width) or ('var', lvalue, shift, mask, width) for a target
        name ; shift and mask are C code (or ints)."""
        k = nodes.Get_Kind(target)
        if k in (K.Simple_Name, K.Selected_Name):
            decl = nodes.Get_Named_Entity(target)
            b = self.binding(decl, target)
            if b.kind == "sigptr":
                return ("sig", self.bc(b), 0, mask(b.ct.width), b.ct.width, b.ct)
            if b.kind == "sig":
                return ("sig", "&" + self.bc(b), 0, mask(b.ct.width), b.ct.width, b.ct)
            return ("var", self.bc(b), 0, mask(b.ct.width), b.ct.width, b.ct)
        if k in (K.Slice_Name, K.Indexed_Name):
            kind, base, shift, m, width, ct = self.target_lvalue(nodes.Get_Prefix(target))
            if ct.kind != "vec":
                raise unsupported(target, "indexing a non-vector target")
            if k == K.Slice_Name:
                lo_pos, w = self.slice_bounds(target, ct)
                return (kind, base, lo_pos, mask(w), w, Vec(w))
            pos = self.index_pos(target, ct)
            if isinstance(pos, int):
                return (kind, base, pos, mask(1), 1, Bit())
            return (kind, base, pos, "(UINT64_C(1) << (%s))" % pos, 1, Bit())
        raise unsupported(target, "assignment target")

    def assign(self, target, value, scope_kind):
        kind, base, shift, m, width, ct = self.target_lvalue(target)
        o = self.out
        whole = isinstance(shift, int) and shift == 0 and width == ct_width_of(self, target)
        v = value.code
        if ct.kind == "int" or value.ct.kind == "int":
            v = "(uint64_t)(%s)" % v if kind == "sig" else v
        if kind == "sig":
            if whole:
                o.line("vs_drive(%s, %s);" % (base, v))
            else:
                o.line("vs_drive_bits(%s, %s, %s, %s);" % (base, shift, m, v))
        else:
            if whole:
                o.line("%s = %s;" % (base, v))
            else:
                o.line("%s = (%s & ~(%s << %s)) | ((%s << %s) & (%s << %s));" % (base, base, m, shift, v, shift, m, shift))

    def s_Simple_Signal_Assignment_Statement(self, s):
        wf = nodes.Get_Waveform_Chain(s)
        if not wf or nodes.Get_Chain(wf):
            raise unsupported(s, "waveform with several elements")
        if nodes.Get_Time(wf):
            raise unsupported(s, "delayed assignment")
        self.assign(nodes.Get_Target(s), self.expr(nodes.Get_We_Value(wf)), "sig")

    def s_Variable_Assignment_Statement(self, s):
        self.assign(nodes.Get_Target(s), self.expr(nodes.Get_Expression(s)), "var")

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
            self.assign(target, self.expr(nodes.Get_We_Value(wf)), "sig")
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
            self.assign(target, self.expr(nodes.Get_We_Value(wf)), "sig")
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

    def s_Case_Statement(self, s):
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
        rng = nodes.Get_Discrete_Range(spec)
        left, right, asc = self.loop_range(rng)
        name = "i_%d" % self.new_label()
        self.bindings[spec] = Binding("local", name, Int())
        lid = self.new_label()
        self.loops = getattr(self, "loops", []) + [(s, lid)]
        if asc:
            o.open("for (int64_t %s = %s; %s <= %s; %s++)" % (name, left, name, right, name))
        else:
            o.open("for (int64_t %s = %s; %s >= %s; %s--)" % (name, left, name, right, name))
        self.stmts(nodes.Get_Sequential_Statement_Chain(s))
        o.line("loop_next_%d:;" % lid)
        o.close()
        o.line("loop_exit_%d:;" % lid)
        self.loops.pop()

    def s_While_Loop_Statement(self, s):
        o = self.out
        lid = self.new_label()
        self.loops = getattr(self, "loops", []) + [(s, lid)]
        c = nodes.Get_Condition(s)
        o.open("while (%s)" % (self.cond(c) if c else "1"))
        self.stmts(nodes.Get_Sequential_Statement_Chain(s))
        o.line("loop_next_%d:;" % lid)
        o.close()
        o.line("loop_exit_%d:;" % lid)
        self.loops.pop()

    def loop_range(self, rng):
        """(left C code, right C code, ascending) of the discrete range of a loop."""
        k = nodes.Get_Kind(rng)
        if k in (K.Integer_Subtype_Definition, K.Enumeration_Subtype_Definition):
            rng = nodes.Get_Range_Constraint(rng)
            k = nodes.Get_Kind(rng)
        if k == K.Range_Expression:
            asc = nodes.Get_Direction(rng) == nodes.DirectionType.To
            return (self.expr(nodes.Get_Left_Limit_Expr(rng)).code, self.expr(nodes.Get_Right_Limit_Expr(rng)).code, asc)
        if k == K.Range_Array_Attribute:
            ct = self.expr(nodes.Get_Prefix(rng)).ct
            if ct.kind != "vec" or ct.width is None:
                raise unsupported(rng, "'range of this prefix")
            if ct.asc:
                return (str(ct.lo), str(ct.hi), True)
            return (str(ct.hi), str(ct.lo), False)
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

    def x_Aggregate(self, n):
        t = type_of(nodes.Get_Type(n))
        if t.kind not in ("vec", "bit"):
            raise unsupported(n, "aggregate of this type")
        w = need_w(n, t.width)
        others = None
        named = []
        pos = []
        ch = nodes.Get_Association_Choices_Chain(n)
        while ch:
            ck = nodes.Get_Kind(ch)
            val = nodes.Get_Associated_Expr(ch)
            if ck == K.Choice_By_Others:
                others = self.expr(val)
            elif ck == K.Choice_By_None:
                pos.append(self.expr(val))
            elif ck == K.Choice_By_Expression:
                named.append((self.static_index(nodes.Get_Choice_Expression(ch), n), 1, self.expr(val)))
            elif ck == K.Choice_By_Range:
                from vtypes import range_of
                left, right, asc = range_of(nodes.Get_Choice_Range(ch))
                lo, hi = (left, right) if asc else (right, left)
                named.append((lo, hi - lo + 1, self.expr(val)))
            else:
                raise unsupported(ch, "aggregate choice")
            ch = nodes.Get_Chain(ch)
        code = "0"
        if others is not None:
            code = "(%s ? %s : 0)" % (others.code, mask(w))
        if pos:
            # positional : the first element is the leftmost
            for i, e in enumerate(pos):
                p = w - 1 - i
                code = "((%s & ~(UINT64_C(1) << %d)) | ((%s & 1) << %d))" % (code, p, e.code, p)
        for idx, count, e in named:
            p = t.pos(idx)
            m = (((1 << count) - 1) << p)
            if count == 1:
                code = "((%s & ~UINT64_C(0x%X)) | ((%s & 1) << %d))" % (code, m, e.code, p)
            else:
                code = "((%s & ~UINT64_C(0x%X)) | (%s ? UINT64_C(0x%X) : 0))" % (code, m, e.code, m)
        return E(code, Vec(w, t.asc, t.lo, t.hi, t.signed) if t.kind == "vec" else t)

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

    def user_call(self, n):
        raise unsupported(n, "call of a user function")

    def user_procedure_call(self, s, call):
        raise unsupported(s, "call of a user procedure")


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
