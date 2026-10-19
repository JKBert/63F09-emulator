"""User functions and procedures.

Each call instantiates a C function for the shapes of its arguments (the widths of the vectors that the
formal parameters leave unconstrained come from the actuals) ; the function is translated once per shape.
A subprogram declared in a package becomes a plain C function of the shared file gen_funcs.c ; one declared
in an architecture, a generate or a process takes the pointer to the structure of that scope as its first
argument, so that it reaches the signals and variables of the scope.
"""

import frontend
import tdefs
from cout import Out
from cops import E
from vtypes import Arr, Bit, Int, Rec, Unsupported, Vec, ctype_sig, ctype_val, is_wide, type_of, unsupported
from pyGHDL.libghdl.vhdl import nodes, nodes_meta

K = nodes.Iir_Kind
F = nodes_meta.fields
M = nodes.Iir_Mode

PKG_FUNCS = {}          # (decl, shape) -> FuncInst : the subprograms of the packages, shared by all entities
_counter = {}


class FuncInst:
    def __init__(self, name, decl, scope):
        self.name = name
        self.decl = decl
        self.scope = scope          # declaring Scope, None for a package
        self.result = None          # CT of the result (functions)
        self.proto = None
        self.text = None


def shape_key(ct):
    if ct.kind == "vec":
        return ("vec", ct.width, ct.asc, ct.lo, ct.hi, ct.signed)
    if ct.kind in ("rec", "arr"):
        return ("c", ct.cname)
    return (ct.kind,)


class Subprograms:
    # --------------------------------------------------------------------- where is it declared

    def decl_scope(self, decl):
        """The Scope that a subprogram sees : None for a package."""
        node = nodes.Get_Parent(decl)
        while node:
            k = nodes.Get_Kind(node)
            if k in (K.Package_Declaration, K.Package_Body):
                return None
            if node in self.scope_of:
                return self.scope_of[node]
            node = nodes.Get_Parent(node)
        return self.scope

    def formals(self, spec):
        out = []
        p = nodes.Get_Interface_Declaration_Chain(spec)
        while p:
            out.append(p)
            p = nodes.Get_Chain(p)
        return out

    def param_class(self, p):
        k = nodes.Get_Kind(p)
        if k == K.Interface_Signal_Declaration:
            return "signal"
        if k == K.Interface_Variable_Declaration:
            return "variable"
        return "constant"

    # --------------------------------------------------------------------- calls

    def actuals_by_formal(self, chain, formals):
        """{formal decl: actual node} of a call, positional or named."""
        out = {}
        pos = 0
        a = chain
        while a:
            f = nodes.Get_Formal(a)
            if f:
                decl = nodes.Get_Named_Entity(f) if nodes.Get_Kind(f) in (K.Simple_Name, K.Selected_Name) else None
                if decl is None:
                    raise unsupported(a, "partial association of a parameter")
            else:
                decl = formals[pos]
            if nodes.Get_Kind(a) != K.Association_Element_Open:
                out[decl] = nodes.Get_Actual(a)
            pos += 1
            a = nodes.Get_Chain(a)
        return out

    def user_call(self, n):
        decl = nodes.Get_Implementation(n)
        code, result = self.call_code(n, decl, nodes.Get_Parameter_Association_Chain(n))
        return E(code, result)

    def user_procedure_call(self, s, call):
        decl = nodes.Get_Implementation(call)
        code, result = self.call_code(call, decl, nodes.Get_Parameter_Association_Chain(call))
        self.out.line(code + ";")

    def call_code(self, n, decl, chain):
        formals = self.formals(decl)
        actuals = self.actuals_by_formal(chain, formals)
        args, cts, shape = [], [], []
        for p in formals:
            cls = self.param_class(p)
            mode = nodes.Get_Mode(p)
            actual = actuals.get(p)
            if actual is None:
                dv = nodes.Get_Default_Value(p)
                if not dv:
                    raise unsupported(n, "parameter %s has no actual" % frontend.ident(p))
                actual = dv
            declared = type_of(nodes.Get_Type(p))
            if cls == "signal":
                kind, code, ct = self.path(actual)
                if kind != "sig":
                    raise unsupported(actual, "signal parameter with an actual that is not a signal")
                args.append("&" + code)
                cts.append(ct)
            elif mode in (M.Out_Mode, M.Inout_Mode):
                kind, code, ct = self.path(actual)
                if kind != "var":
                    raise unsupported(actual, "variable parameter with an actual that is not a variable")
                args.append("&" + code)
                cts.append(ct)
            else:
                e = self.expr(actual)
                args.append(e.code)
                cts.append(e.ct)
            if declared.kind == "vec" and declared.width is None:
                shape.append(shape_key(cts[-1]))
            else:
                shape.append(None)
        inst = self.sub_instance(decl, tuple(shape), cts)
        pre = []
        if inst.scope is not None:
            pre.append(self.path_to(inst.scope))
        return "%s(%s)" % (inst.name, ", ".join(pre + args)), inst.result

    # --------------------------------------------------------------------- instances

    def sub_instance(self, decl, shape, arg_cts):
        scope = self.decl_scope(decl)
        registry = PKG_FUNCS if scope is None else self.local_funcs
        key = (decl, shape)
        if key in registry:
            inst = registry[key]
            if inst.result is None and inst.is_function and inst.text is None:
                raise unsupported(decl, "recursive function whose result type is not known")
            return inst
        base = frontend.ident(decl).lower()
        base = "".join(c if c.isalnum() or c == "_" else "_" for c in base)
        n = _counter.get(base, 0)
        _counter[base] = n + 1
        is_function = nodes.Get_Kind(decl) == K.Function_Declaration
        inst = FuncInst("%s_%d" % (("f_" if is_function else "p_") + base, n), decl, scope)
        inst.is_function = is_function
        registry[key] = inst
        self.translate_body(inst, arg_cts)
        return inst

    def translate_body(self, inst, arg_cts):
        decl = inst.decl
        body = nodes.Get_Subprogram_Body(decl)
        if not body:
            raise unsupported(decl, "subprogram without a body")
        saved = (self.out, self.scope, getattr(self, "loops", []), getattr(self, "func", None))
        self.out = Out()
        if inst.scope is not None:
            self.scope = inst.scope
        else:
            self.scope = _PackageScope()
        self.loops = []
        self.func = inst
        params = []
        for p, ct in zip(self.formals(decl), arg_cts):
            cls = self.param_class(p)
            mode = nodes.Get_Mode(p)
            name = "a_" + frontend.ident(p).lower()
            declared = type_of(nodes.Get_Type(p))
            if not (declared.kind == "vec" and declared.width is None):
                ct = declared
            from cgen import Binding
            if cls == "signal":
                params.append("%s *%s" % (ctype_sig(ct), name))
                self.bindings[p] = Binding("sigptr", name, ct, None)
            elif mode in (M.Out_Mode, M.Inout_Mode):
                params.append("%s *%s" % (ctype_val(ct), name))
                self.bindings[p] = Binding("var", "(*%s)" % name, ct, None)
            else:
                params.append("%s %s" % (ctype_val(ct), name))
                self.bindings[p] = Binding("var", name, ct, None)
        self.func_result = None
        self.func_is_function = inst.is_function
        # a declared, constrained result type is known at once
        if inst.is_function:
            try:
                rt = type_of(nodes.Get_Return_Type(decl))
                if not (rt.kind == "vec" and rt.width is None):
                    self.func_result = rt
                    inst.result = rt
            except Unsupported:
                pass
        o = self.out
        header_pos = len(o.lines)
        o.level = 1
        self.local_declarations(nodes.Get_Declaration_Chain(body))
        self.stmts(nodes.Get_Sequential_Statement_Chain(body))
        o.level = 0
        if inst.is_function and self.func_result is None:
            raise unsupported(decl, "function without a return statement")
        inst.result = self.func_result if inst.is_function else None
        ret = ctype_val(inst.result) if inst.is_function else "void"
        pre = ["%s *self" % inst.scope.struct] if inst.scope is not None else []
        inst.proto = "%s %s(%s)" % (ret, inst.name, ", ".join(pre + params) if (pre or params) else "void")
        text = Out()
        text.line(("static " if inst.scope is not None else "") + inst.proto)
        text.line("{")
        text.lines.extend(o.lines)
        text.line("}")
        inst.text = text.text()
        self.out, self.scope, self.loops, self.func = saved

    def local_declarations(self, chain):
        from cgen import Binding
        o = self.out
        d = chain
        while d:
            k = nodes.Get_Kind(d)
            if k == K.Variable_Declaration:
                ct = type_of(nodes.Get_Type(d))
                name = "v_%s_%d" % (frontend.ident(d).lower(), id(d) % 100000)
                init = nodes.Get_Default_Value(d)
                from gen import zero
                o.line("%s %s = %s;" % (ctype_val(ct), name, self.expr(init).code if init else zero(ct)))
                self.bindings[d] = Binding("var", name, ct, None)
            elif k == K.Constant_Declaration:
                ct = type_of(nodes.Get_Type(d))
                name = "c_%s_%d" % (frontend.ident(d).lower(), id(d) % 100000)
                o.line("const %s %s = %s;" % (ctype_val(ct), name, self.expr(nodes.Get_Default_Value(d)).code))
                self.bindings[d] = Binding("var", name, ct, None)
            elif k in (K.Type_Declaration, K.Subtype_Declaration, K.Anonymous_Type_Declaration, K.Attribute_Declaration,
                       K.Attribute_Specification, K.Use_Clause, K.Function_Body, K.Procedure_Body):
                pass
            elif k in (K.Function_Declaration, K.Procedure_Declaration):
                pass
            else:
                raise unsupported(d, "declaration in a subprogram")
            d = nodes.Get_Chain(d)

    def s_Return_Statement(self, s):
        e = nodes.Get_Expression(s)
        if e:
            v = self.expr(e)
            if self.func_result is None:
                self.func_result = v.ct
                self.func.result = v.ct
            self.out.line("return %s;" % v.code)
        else:
            self.out.line("return;")


class _PackageScope:
    """Stand-in for the scope while a package subprogram is translated : it owns nothing."""
    depth = 0
    struct = "void"
