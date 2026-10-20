"""C definitions of the composite types (records and arrays) : the value structure, the structure of
signals (one vs_sig per scalar), and the functions that read, drive, register and list the leaves."""

from cout import Out
from vtypes import COMPOSITES, ctype_sig, ctype_val, is_wide, nwords


def get_expr(st, ct):
    """Value of the signal storage `st` (a C lvalue)."""
    if is_wide(ct):
        return "vs_w_get(%s.w, %d)" % (st, nwords(ct))
    if ct.kind in ("rec", "arr"):
        return "%s_get(&%s)" % (ct.cname, st)
    if ct.kind == "int":
        return "(int64_t) %s.cur" % st
    if ct.kind == "enum":
        return "(uint32_t) %s.cur" % st
    return "%s.cur" % st


def drive_stmt(st, ct, v):
    if is_wide(ct):
        return "vs_w_drive(%s.w, %d, %s);" % (st, nwords(ct), v)
    if ct.kind in ("rec", "arr"):
        return "%s_drive(&%s, %s);" % (ct.cname, st, v)
    return "vs_drive(&%s, (uint64_t) (%s));" % (st, v)


def register_stmt(st, ct, v):
    if is_wide(ct):
        return "vs_w_register(k, %s.w, %d, %s);" % (st, nwords(ct), v)
    if ct.kind in ("rec", "arr"):
        return "%s_register(k, &%s, %s);" % (ct.cname, st, v)
    return "vs_register_signal(k, &%s, (uint64_t) (%s));" % (st, v)


def leaves_stmt(st, ct):
    if is_wide(ct):
        return "{ size_t j; for (j = 0; j < %d; j++) { out[n++] = &%s.w[j]; } }" % (nwords(ct), st)
    if ct.kind in ("rec", "arr"):
        return "n += %s_leaves(&%s, out + n);" % (ct.cname, st)
    return "out[n++] = &%s;" % st


def eq_expr(a, b, ct):
    if is_wide(ct):
        return "vs_w_eq(%s, %s)" % (a, b)
    if ct.kind in ("rec", "arr"):
        return "%s_eq(%s, %s)" % (ct.cname, a, b)
    return "(%s == %s)" % (a, b)


def zero_value(ct):
    """C code of the initial value of an object of the type when it is not 0, else None."""
    if ct.kind in ("rec", "arr"):
        return "%s_zero()" % ct.cname if has_nonzero(ct) else None
    if ct.kind == "int" and ct.left:
        return "INT64_C(%d)" % ct.left
    return None


def has_nonzero(ct):
    if ct.kind == "rec":
        return any(has_nonzero(f[2]) for f in ct.fields)
    if ct.kind == "arr":
        return has_nonzero(ct.elem)
    return ct.kind == "int" and bool(ct.left)


def members(ct):
    """[(name, CT, count)] : the fields of a record, or the elements of an array (count N)."""
    if ct.kind == "rec":
        return [(f[0], f[2], None) for f in ct.fields]
    return [("a", ct.elem, ct.length)]


def define(ct):
    o = Out()
    cn = ct.cname
    o.open("typedef struct %s" % cn)
    for name, mct, n in members(ct):
        o.line("%s %s%s;" % (ctype_val(mct), name, "[%d]" % n if n else ""))
    o.close(" %s;" % cn)
    o.open("typedef struct %s_s" % cn)
    for name, mct, n in members(ct):
        o.line("%s %s%s;" % (ctype_sig(mct), name, "[%d]" % n if n else ""))
    o.close(" %s_s;" % cn)
    o.line()

    def fn(head, builder):
        """A function : the loop index is declared only when the body uses it."""
        tmp = Out()
        tmp.level = o.level + 1
        builder(tmp)
        o.open(head)
        if any("[i]" in l or "i < " in l for l in tmp.lines):
            o.line("size_t i;")
        o.lines.extend(tmp.lines)
        o.close()
        o.line()

    def each(out, body):
        """Calls body(member suffix, CT) for every member and element."""
        for name, mct, n in members(ct):
            if n:
                out.open("for (i = 0; i < %d; i++)" % n)
                body("%s[i]" % name, mct)
                out.close()
            else:
                body(name, mct)

    def zero(out):
        out.line("%s v;" % cn)
        out.line("memset(&v, 0, sizeof(v));")
        for name, mct, n in members(ct):
            init = zero_value(mct)
            if init is None:
                continue
            if n:
                out.open("for (i = 0; i < %d; i++)" % n)
                out.line("v.%s[i] = %s;" % (name, init))
                out.close()
            else:
                out.line("v.%s = %s;" % (name, init))
        out.line("return v;")

    fn("static inline %s %s_zero(void)" % (cn, cn), zero)

    if ct.kind == "arr":
        def fill(out):
            out.line("%s v;" % cn)
            out.open("for (i = 0; i < %d; i++)" % ct.length)
            out.line("v.a[i] = e;")
            out.close()
            out.line("return v;")

        fn("static inline %s %s_fill(%s e)" % (cn, cn, ctype_val(ct.elem)), fill)
        fn("static inline %s %s_put(%s v, size_t pos, %s e)" % (cn, cn, cn, ctype_val(ct.elem)),
           lambda out: (out.line("v.a[pos] = e;"), out.line("return v;")))
    else:
        for fname, vname, fct in ct.fields:
            fn("static inline %s %s_with_%s(%s v, %s e)" % (cn, cn, fname, cn, ctype_val(fct)),
               lambda out: (out.line("v.%s = e;" % fname), out.line("return v;")))

    def get(out):
        out.line("%s v;" % cn)
        each(out, lambda m, mct: out.line("v.%s = %s;" % (m, get_expr("s->" + m, mct))))
        out.line("return v;")

    fn("static inline %s %s_get(const %s_s *s)" % (cn, cn, cn), get)
    fn("static inline void %s_drive(%s_s *s, %s v)" % (cn, cn, cn),
       lambda out: each(out, lambda m, mct: out.line(drive_stmt("s->" + m, mct, "v." + m))))
    fn("static inline void %s_register(vs_kernel *k, %s_s *s, %s v)" % (cn, cn, cn),
       lambda out: each(out, lambda m, mct: out.line(register_stmt("s->" + m, mct, "v." + m))))

    def leaves(out):
        out.line("size_t n = 0;")
        each(out, lambda m, mct: out.line(leaves_stmt("s->" + m, mct)))
        out.line("return n;")

    fn("static inline size_t %s_leaves(%s_s *s, vs_sig **out)" % (cn, cn), leaves)

    def eq(out):
        each(out, lambda m, mct: out.line("if (!%s) { return 0; }" % eq_expr("a." + m, "b." + m, mct)))
        out.line("return 1;")

    fn("static inline int %s_eq(%s a, %s b)" % (cn, cn, cn), eq)
    return o.text()


CONST_AGGS = {}         # name -> (C type, code) : constant aggregates, built once (see hoist)


def hoist(cname, code):
    """Name of a function returning a pointer to the constant `code` of type `cname`, built the first time it is called.
    A lookup table written as an aggregate would otherwise be rebuilt, element by element, at every evaluation."""
    import hashlib
    name = "agg_" + hashlib.sha1((cname + code).encode()).hexdigest()[:12]
    CONST_AGGS[name] = (cname, code)
    return name


def header():
    o = Out()
    o.line("/*")
    o.line(" * Generated by tools/vhdl2c : the record and array types of the VHDL design. Do not edit.")
    o.line(" * See docs/GENERATION.md.")
    o.line(" */")
    o.line()
    o.line("#ifndef GEN_TYPES_H")
    o.line("#define GEN_TYPES_H")
    o.line()
    o.line('#include <string.h>')
    o.line('#include "vwide.h"')
    o.line()
    text = o.text()
    for ct in COMPOSITES:
        text += define(ct)
    for name, (cname, code) in sorted(CONST_AGGS.items()):
        text += ("static inline const %s *%s(void)\n{\n    static %s v;\n    static int built;\n\n    if (!built)\n    {\n"
                 "        v = %s;\n        built = 1;\n    }\n    return &v;\n}\n\n") % (cname, name, cname, code)
    return text + "#endif\n"
