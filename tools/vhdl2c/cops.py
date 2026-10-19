"""Operators and predefined functions of the VHDL subset, translated from their implicit definition.

Values : bit and vector expressions are uint64_t, masked to their width ; integers are int64_t.
"""

import re

import frontend
from vtypes import Bit, Int, Unsupported, Vec, unsupported, type_of
from pyGHDL.libghdl.vhdl import nodes

K = nodes.Iir_Kind
P = nodes.Iir_Predefined


def mask(width):
    return "UINT64_C(0x%X)" % ((1 << width) - 1) if width < 64 else "UINT64_MAX"


class E:
    """A translated expression : C code and CT."""

    def __init__(self, code, ct):
        self.code = code
        self.ct = ct


def uval(e):
    """The value as an unsigned 64-bit number (zero-extended)."""
    if e.ct.kind == "int":
        return "(uint64_t)(%s)" % e.code
    return e.code


def ival(e):
    """The value as a signed 64-bit number : integers as they are, signed vectors sign-extended."""
    if e.ct.kind == "int":
        return e.code
    if e.ct.kind == "vec" and e.ct.signed:
        return "vs_sext(%s, %d)" % (e.code, e.ct.width)
    return "(int64_t)(%s)" % e.code


def need_width(n, w):
    if w is None or w > 512:
        raise unsupported(n, "vector wider than 512 bits")
    return w


def wide(e):
    """True when the expression is a vector wider than 64 bits : its code is a vs_w."""
    return e.ct.kind == "vec" and e.ct.width is not None and e.ct.width > 64


def WS(e):
    """The code of the expression as a vs_w, sign-extended (a signed vector, or an integer)."""
    if wide(e):
        return "vs_w_sext(%s, %d)" % (e.code, e.ct.width)
    if e.ct.kind == "int":
        return "vs_w_from_signed(%s, 64)" % e.code
    if e.ct.kind == "vec" and e.ct.signed:
        return "vs_w_from_signed(vs_sext(%s, %d), 64)" % (e.code, e.ct.width)
    return "vs_w_from(%s)" % e.code


def W(e):
    """The code of the expression as a vs_w (zero-extended when it is narrow)."""
    if wide(e):
        return e.code
    if e.ct.kind == "int":
        return "vs_w_from((uint64_t)(%s))" % e.code
    return "vs_w_from(%s)" % e.code


INT_BIN = {"Integer_Plus": "+", "Integer_Minus": "-", "Integer_Mul": "*", "Integer_Div": "/", "Integer_Rem": "%"}
CMP = {"Eq": "==", "Ne": "!=", "Lt": "<", "Le": "<=", "Gt": ">", "Ge": ">="}
INT_CMP = {"Integer_Equality": "==", "Integer_Inequality": "!=", "Integer_Less": "<", "Integer_Less_Equal": "<=",
           "Integer_Greater": ">", "Integer_Greater_Equal": ">="}


class Ops:
    # --------------------------------------------------------------------- operator nodes

    def operator(self, n):
        impl = nodes.Get_Implementation(n)
        pre = P(nodes.Get_Implicit_Definition(impl))
        k = frontend.kind_name(n)
        if k.startswith("Reduction_"):
            e = self.reduce_dynamic_slice(n, k)
            if e is not None:
                return e
        if frontend.has_field(nodes.Get_Kind(n), frontend.nodes_meta.fields.Left):
            args = [self.expr(nodes.Get_Left(n)), self.expr(nodes.Get_Right(n))]
        else:
            args = [self.expr(nodes.Get_Operand(n))]
        return self.apply(n, pre, args)

    def reduce_dynamic_slice(self, n, k):
        """Reduction of a slice whose width depends on a generate parameter (`or FGHIT(0 to g - 1)`) : the mask is
        computed when the design is built. None when the operand is not such a slice."""
        op = nodes.Get_Operand(n)
        if nodes.Get_Kind(op) != K.Slice_Name:
            return None
        pe = self.expr(nodes.Get_Prefix(op))
        if pe.ct.kind != "vec" or wide(pe):
            return None
        try:
            self.slice_bounds(op, pe.ct)
            return None
        except Unsupported:
            pass
        rng = nodes.Get_Suffix(op)
        if nodes.Get_Kind(rng) in (K.Integer_Subtype_Definition, K.Enumeration_Subtype_Definition):
            rng = nodes.Get_Range_Constraint(rng)
        asc = nodes.Get_Direction(rng) == nodes.DirectionType.To
        if asc != pe.ct.asc:
            raise unsupported(n, "slice direction differs from the vector's")
        le = self.expr(nodes.Get_Left_Limit_Expr(rng)).code
        re_ = self.expr(nodes.Get_Right_Limit_Expr(rng)).code
        lo, hi = (le, re_) if asc else (re_, le)
        pos = "(%d - (%s))" % (pe.ct.hi, hi) if asc else "((%s) - %d)" % (lo, pe.ct.lo)
        width = "((%s) - (%s) + 1)" % (hi, lo)
        part = "((%s >> %s) & ((UINT64_C(1) << %s) - 1))" % (pe.code, pos, width)
        full = "((UINT64_C(1) << %s) - 1)" % width
        red = {"Reduction_Or_Operator": "(%s != 0)", "Reduction_Nor_Operator": "(%s == 0)",
               "Reduction_And_Operator": "(%s == " + full + ")", "Reduction_Nand_Operator": "(%s != " + full + ")",
               "Reduction_Xor_Operator": "(__builtin_parityll(%s) != 0)",
               "Reduction_Xnor_Operator": "(__builtin_parityll(%s) == 0)"}[k]
        return E("(uint64_t)" + red % part, Bit())

    def call_args(self, n):
        a = nodes.Get_Parameter_Association_Chain(n)
        out = []
        while a:
            out.append(self.expr(nodes.Get_Actual(a)))
            a = nodes.Get_Chain(a)
        return out

    def x_Function_Call(self, n):
        impl = nodes.Get_Implementation(n)
        pre = P(nodes.Get_Implicit_Definition(impl))
        if pre in (P.Ieee_1164_Rising_Edge, P.Ieee_1164_Falling_Edge):
            arg = list(self.assoc_actuals(nodes.Get_Parameter_Association_Chain(n)))[0]
            ptr, shift, w, ct = self.sigptr(arg)
            fn = "vs_rising" if pre == P.Ieee_1164_Rising_Edge else "vs_falling"
            return E("%s(%s)" % (fn, ptr), Bit())
        if pre == P.PNone:
            return self.user_call(n)
        return self.apply(n, pre, self.call_args(n), static_args=self.static_call_args(n))

    def static_call_args(self, n):
        """Constant value of each argument (None when it is not constant) : the widths of the
        results of to_unsigned, resize... depend on them."""
        from vtypes import const_int, Unsupported
        out = []
        a = nodes.Get_Parameter_Association_Chain(n)
        while a:
            try:
                out.append(const_int(nodes.Get_Actual(a)))
            except Unsupported:
                out.append(None)
            a = nodes.Get_Chain(a)
        return out

    # --------------------------------------------------------------------- predefined

    def apply(self, n, pre, a, static_args=None):
        name = pre.name
        if name in INT_BIN:
            return E("(%s %s %s)" % (ival(a[0]), INT_BIN[name], ival(a[1])), Int())
        if name == "Integer_Mod":
            return E("vs_mod(%s, %s)" % (ival(a[0]), ival(a[1])), Int())
        if name == "Integer_Exp":
            return E("vs_ipow(%s, %s)" % (ival(a[0]), ival(a[1])), Int())
        if name == "Integer_Negation":
            return E("(-%s)" % ival(a[0]), Int())
        if name == "Integer_Absolute":
            return E("((%s) < 0 ? -(%s) : (%s))" % ((ival(a[0]),) * 3), Int())
        if name in INT_CMP:
            return E("(%s %s %s)" % (ival(a[0]), INT_CMP[name], ival(a[1])), Bit())
        if name in ("Enum_Equality", "Array_Equality", "Record_Equality", "Enum_Inequality", "Array_Inequality",
                    "Record_Inequality"):
            neg = name.endswith("Inequality")
            if a[0].ct.kind in ("rec", "arr") or wide(a[0]) or wide(a[1]):
                if a[0].ct.kind in ("rec", "arr"):
                    code = "%s_eq(%s, %s)" % (a[0].ct.cname, a[0].code, a[1].code)
                else:
                    code = "vs_w_eq(%s, %s)" % (W(a[0]), W(a[1]))
                return E("(!%s)" % code if neg else code, Bit())
            return E("(%s %s %s)" % (a[0].code, "!=" if neg else "==", a[1].code), Bit())
        m = re.match(r"(Boolean|Ieee_1164_Scalar)_(And|Or|Xor|Nand|Nor|Xnor|Not)$", name)
        if m:
            return self.bitwise(m.group(2), a, 1)
        m = re.match(r"Ieee_1164_Vector_(And|Or|Xor|Nand|Nor|Xnor|Not)$", name)
        if m:
            return self.bitwise(m.group(1), a, a[0].ct.width)
        m = re.match(r"Ieee_1164_(And|Or|Xor|Nand|Nor|Xnor)_Suv$", name)
        if m:
            return self.reduction(m.group(1), a[0], n)
        if name in ("Array_Array_Concat", "Array_Element_Concat", "Element_Array_Concat", "Element_Element_Concat"):
            return self.concat(n, a)
        if name.startswith("Ieee_Std_Logic_Unsigned_"):
            return self.slv_unsigned(n, name[len("Ieee_Std_Logic_Unsigned_"):], a)
        if name.startswith("Ieee_Std_Logic_Arith_"):
            return self.slv_arith(n, name[len("Ieee_Std_Logic_Arith_"):], a, static_args)
        if name.startswith("Ieee_Numeric_Std_"):
            return self.numeric_std(n, name[len("Ieee_Numeric_Std_"):], a, static_args)
        raise unsupported(n, "predefined function %s" % name)

    def bitwise(self, op, a, w):
        if wide(a[0]) or wide(a[-1]):
            ww = a[0].ct.width if wide(a[0]) else a[-1].ct.width
            if op == "Not":
                return E("vs_w_not(%s, %d)" % (W(a[0]), ww), a[0].ct)
            fn = {"And": "vs_w_and", "Nand": "vs_w_and", "Or": "vs_w_or", "Nor": "vs_w_or", "Xor": "vs_w_xor", "Xnor": "vs_w_xor"}[op]
            code = "%s(%s, %s)" % (fn, W(a[0]), W(a[1]))
            if op in ("Nand", "Nor", "Xnor"):
                code = "vs_w_not(%s, %d)" % (code, ww)
            return E(code, a[0].ct if wide(a[0]) else a[-1].ct)
        m = mask(w)
        ct = a[0].ct if a[0].ct.kind in ("bit", "vec") else Bit()
        if op == "Not":
            return E("(~%s & %s)" % (a[0].code, m), ct)
        base = {"And": "&", "Nand": "&", "Or": "|", "Nor": "|", "Xor": "^", "Xnor": "^"}[op]
        code = "(%s %s %s)" % (a[0].code, base, a[1].code)
        if op in ("Nand", "Nor", "Xnor"):
            code = "(~%s & %s)" % (code, m)
        return E(code, ct)

    def reduction(self, op, e, n):
        w = need_width(n, e.ct.width)
        if wide(e):
            if op in ("Or", "Nor"):
                code = "(!vs_w_is_zero(%s))" % e.code
            elif op in ("And", "Nand"):
                code = "vs_w_eq(%s, vs_w_ones(%d))" % (e.code, w)
            else:
                code = "vs_w_parity(%s)" % e.code
            if op in ("Nor", "Nand", "Xnor"):
                code = "(%s ^ 1)" % code
            return E(code, Bit())
        if op in ("Or", "Nor"):
            code = "(%s != 0)" % e.code
        elif op in ("And", "Nand"):
            code = "(%s == %s)" % (e.code, mask(w))
        else:
            code = "vs_parity(%s)" % e.code
        if op in ("Nor", "Nand", "Xnor"):
            code = "(%s ^ 1)" % code
        return E(code, Bit())

    def concat(self, n, a):
        for e in a:
            if e.ct.kind not in ("bit", "vec"):
                raise unsupported(n, "concatenation of these types")
        w = sum(need_width(n, e.ct.width) for e in a)
        if w > 64:
            code = W(a[0])
            for e in a[1:]:
                code = "vs_w_cat(%s, %s, %d)" % (code, W(e), e.ct.width)
            return E(code, Vec(w))
        code = "(uint64_t)(%s)" % a[0].code
        for e in a[1:]:
            code = "((%s << %d) | %s)" % (code, e.ct.width, e.code)
        return E(code, Vec(w))

    def wide_compare(self, op, a, signed=False):
        width = max(e.ct.width for e in a if e.ct.kind == "vec")
        if signed:
            x, y = WS(a[0]), WS(a[1])
            less = "vs_w_slt(%%s, %%s, %d)" % width
        else:
            x, y = W(a[0]), W(a[1])
            less = "vs_w_ult(%s, %s)"
        eq = "vs_w_eq(%s, %s)"
        return {"Eq": eq, "Ne": "(!%s)" % eq, "Lt": less, "Le": "(!%s)" % less, "Gt": less, "Ge": "(!%s)" % less}[op] % \
            ((y, x) if op in ("Gt", "Le") else (x, y))

    # std_logic_unsigned : the vectors are numbers, the result takes the width of the widest vector
    def slv_unsigned(self, n, name, a):
        m = re.match(r"(Add|Sub|Mul)_(Slv|Int|Log)_(Slv|Int|Log)$", name)
        if m:
            op = {"Add": "+", "Sub": "-", "Mul": "*"}[m.group(1)]
            vecs = [e for e in a if e.ct.kind == "vec"]
            w = need_width(n, max(e.ct.width for e in vecs))
            if m.group(1) == "Mul":
                w = need_width(n, sum(e.ct.width for e in vecs))
            if w > 64:
                fn = {"Add": "vs_w_add", "Sub": "vs_w_sub", "Mul": "vs_w_mul"}[m.group(1)]
                return E("%s(%s, %s, %d)" % (fn, W(a[0]), W(a[1]), w), Vec(w))
            return E("((%s %s %s) & %s)" % (uval(a[0]), op, uval(a[1]), mask(w)), Vec(w))
        m = re.match(r"(Eq|Ne|Lt|Le|Gt|Ge)_(Slv|Int)_(Slv|Int)$", name)
        if m:
            if wide(a[0]) or wide(a[1]):
                return E(self.wide_compare(m.group(1), a), Bit())
            return E("(%s %s %s)" % (uval(a[0]), CMP[m.group(1)], uval(a[1])), Bit())
        if name.startswith("Conv_Integer"):
            return E("(int64_t)(%s)" % a[0].code, Int())
        raise unsupported(n, "std_logic_unsigned function %s" % name)

    def slv_arith(self, n, name, a, static_args):
        if name == "Conv_Vector_Int":                  # conv_std_logic_vector(int, size)
            w = static_args[1] if static_args and len(static_args) > 1 else None
            if w is None:
                raise unsupported(n, "conv_std_logic_vector with a size that is not constant")
            return E("((uint64_t)%s & %s)" % (ival(a[0]), mask(w)), Vec(w))
        if name == "Conv_Integer_Log":
            return E("(int64_t)(%s)" % a[0].code, Int())
        raise unsupported(n, "std_logic_arith function %s" % name)

    # numeric_std
    def numeric_std(self, n, name, a, static_args):
        if name == "Toint_Uns_Nat":
            return E("(int64_t)(%s)" % a[0].code, Int())
        if name == "Toint_Sgn_Int":
            return E(ival(a[0]), Int())
        m = re.match(r"Touns_Nat_Nat_Uns$", name)
        if m:
            w = static_args[1] if static_args and len(static_args) > 1 else None
            if w is None:
                raise unsupported(n, "to_unsigned with a size that is not constant")
            return E("((uint64_t)%s & %s)" % (ival(a[0]), mask(w)), Vec(w, False, 0, w - 1, False))
        m = re.match(r"Tosgn_Int_Nat_Sgn$", name)
        if m:
            w = static_args[1] if static_args and len(static_args) > 1 else None
            if w is None:
                raise unsupported(n, "to_signed with a size that is not constant")
            return E("((uint64_t)%s & %s)" % (ival(a[0]), mask(w)), Vec(w, False, 0, w - 1, True))
        m = re.match(r"(Add|Sub|Mul)_(Uns|Sgn|Nat|Int)_(Uns|Sgn|Nat|Int)$", name)
        if m:
            op = {"Add": "+", "Sub": "-", "Mul": "*"}[m.group(1)]
            vecs = [e for e in a if e.ct.kind == "vec"]
            signed = vecs[0].ct.signed
            w = max(e.ct.width for e in vecs)
            if m.group(1) == "Mul":
                w = sum(e.ct.width for e in vecs)
            need_width(n, w)
            if w > 64:
                fn = {"Add": "vs_w_add", "Sub": "vs_w_sub", "Mul": "vs_w_mul"}[m.group(1)]
                conv = WS if signed else W
                return E("%s(%s, %s, %d)" % (fn, conv(a[0]), conv(a[1]), w), Vec(w, False, 0, w - 1, signed, "signed" if signed else "unsigned"))
            if signed:
                code = "((uint64_t)(%s %s %s) & %s)" % (ival(a[0]), op, ival(a[1]), mask(w))
            else:
                code = "((%s %s %s) & %s)" % (uval(a[0]), op, uval(a[1]), mask(w))
            return E(code, Vec(w, False, 0, w - 1, signed))
        m = re.match(r"Neg_Sgn$", name)
        if m:
            w = a[0].ct.width
            if w > 64:
                return E("vs_w_neg(%s, %d)" % (a[0].code, w), Vec(w, False, 0, w - 1, True, "signed"))
            return E("((uint64_t)(-%s) & %s)" % (ival(a[0]), mask(w)), Vec(w, False, 0, w - 1, True))
        m = re.match(r"(Eq|Ne|Lt|Le|Gt|Ge)_(Uns|Sgn|Nat|Int)_(Uns|Sgn|Nat|Int)$", name)
        if m:
            signed = any(x == "Sgn" or x == "Int" for x in (m.group(2), m.group(3)))
            if wide(a[0]) or wide(a[1]):
                if signed:
                    return E(self.wide_compare(m.group(1), a, signed=True), Bit())
                return E(self.wide_compare(m.group(1), a), Bit())
            lhs, rhs = (ival(a[0]), ival(a[1])) if signed else (uval(a[0]), uval(a[1]))
            return E("(%s %s %s)" % (lhs, CMP[m.group(1)], rhs), Bit())
        m = re.match(r"Shf_(Left|Right)_(Uns|Sgn)_Nat$", name)
        if m:
            e = a[0]
            w = e.ct.width
            if wide(e):
                if m.group(1) == "Left":
                    return E("vs_w_shl(%s, %s, %d)" % (e.code, ival(a[1]), w), e.ct)
                if m.group(2) == "Sgn":
                    return E("vs_w_sar(%s, %s, %d)" % (e.code, ival(a[1]), w), e.ct)
                return E("vs_w_shr(%s, %s)" % (e.code, ival(a[1])), e.ct)
            if m.group(1) == "Left":
                return E("(vs_shl(%s, %s) & %s)" % (e.code, ival(a[1]), mask(w)), e.ct)
            if m.group(2) == "Sgn":
                return E("((uint64_t)(%s >> (%s)) & %s)" % (ival(e), ival(a[1]), mask(w)), e.ct)
            return E("vs_shr(%s, %s)" % (e.code, ival(a[1])), e.ct)
        m = re.match(r"Srl_(Uns|Sgn)_Int$", name)
        if m:
            return E("vs_shr(%s, %s)" % (a[0].code, ival(a[1])), a[0].ct)
        m = re.match(r"Resize_(Uns|Sgn)_Nat$", name)
        if m:
            w = static_args[1] if static_args and len(static_args) > 1 else None
            if w is None:
                raise unsupported(n, "resize with a size that is not constant")
            signed = m.group(1) == "Sgn"
            if signed:
                return E("((uint64_t)%s & %s)" % (ival(a[0]), mask(w)), Vec(w, False, 0, w - 1, True))
            return E("(%s & %s)" % (a[0].code, mask(w)), Vec(w, False, 0, w - 1, False))
        raise unsupported(n, "numeric_std function %s" % name)

    # --------------------------------------------------------------------- operator node kinds

    def x_Addition_Operator(self, n):
        return self.operator(n)

    x_Substraction_Operator = x_Addition_Operator
    x_Multiplication_Operator = x_Addition_Operator
    x_Division_Operator = x_Addition_Operator
    x_Modulus_Operator = x_Addition_Operator
    x_Remainder_Operator = x_Addition_Operator
    x_Exponentiation_Operator = x_Addition_Operator
    x_Negation_Operator = x_Addition_Operator
    x_Absolute_Operator = x_Addition_Operator
    x_Equality_Operator = x_Addition_Operator
    x_Inequality_Operator = x_Addition_Operator
    x_Less_Than_Operator = x_Addition_Operator
    x_Less_Than_Or_Equal_Operator = x_Addition_Operator
    x_Greater_Than_Operator = x_Addition_Operator
    x_Greater_Than_Or_Equal_Operator = x_Addition_Operator
    x_And_Operator = x_Addition_Operator
    x_Or_Operator = x_Addition_Operator
    x_Xor_Operator = x_Addition_Operator
    x_Nand_Operator = x_Addition_Operator
    x_Nor_Operator = x_Addition_Operator
    x_Xnor_Operator = x_Addition_Operator
    x_Not_Operator = x_Addition_Operator
    x_Reduction_Or_Operator = x_Addition_Operator
    x_Reduction_And_Operator = x_Addition_Operator
    x_Reduction_Xor_Operator = x_Addition_Operator
    x_Reduction_Nor_Operator = x_Addition_Operator
    x_Reduction_Nand_Operator = x_Addition_Operator
    x_Reduction_Xnor_Operator = x_Addition_Operator
    x_Concatenation_Operator = x_Addition_Operator
    x_Srl_Operator = x_Addition_Operator
    x_Sll_Operator = x_Addition_Operator
    x_Sra_Operator = x_Addition_Operator
    x_Sla_Operator = x_Addition_Operator
