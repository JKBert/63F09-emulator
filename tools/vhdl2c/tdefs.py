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

    def each(body):
        """Calls body(member suffix of the storage, of the value, CT) for every member and element."""
        for name, mct, n in members(ct):
            if n:
                o.open("for (i = 0; i < %d; i++)" % n)
                body("%s[i]" % name, mct)
                o.close()
            else:
                body(name, mct)

    o.open("static inline %s %s_zero(void)" % (cn, cn))
    o.line("%s v;" % cn)
    o.line("memset(&v, 0, sizeof(v));")
    o.line("return v;")
    o.close()
    o.line()
    if ct.kind == "arr":
        o.open("static inline %s %s_fill(%s e)" % (cn, cn, ctype_val(ct.elem)))
        o.line("%s v;" % cn)
        o.line("size_t i;")
        o.open("for (i = 0; i < %d; i++)" % ct.length)
        o.line("v.a[i] = e;")
        o.close()
        o.line("return v;")
        o.close()
        o.line()
        o.open("static inline %s %s_put(%s v, size_t pos, %s e)" % (cn, cn, cn, ctype_val(ct.elem)))
        o.line("v.a[pos] = e;")
        o.line("return v;")
        o.close()
        o.line()
    else:
        for fname, vname, fct in ct.fields:
            o.open("static inline %s %s_with_%s(%s v, %s e)" % (cn, cn, fname, cn, ctype_val(fct)))
            o.line("v.%s = e;" % fname)
            o.line("return v;")
            o.close()
            o.line()
    o.open("static inline %s %s_get(const %s_s *s)" % (cn, cn, cn))
    o.line("%s v;" % cn)
    if any(n for _, _, n in members(ct)):
        o.line("size_t i;")
    each(lambda m, mct: o.line("v.%s = %s;" % (m, get_expr("s->" + m, mct))))
    o.line("return v;")
    o.close()
    o.line()
    o.open("static inline void %s_drive(%s_s *s, %s v)" % (cn, cn, cn))
    if any(n for _, _, n in members(ct)):
        o.line("size_t i;")
    each(lambda m, mct: o.line(drive_stmt("s->" + m, mct, "v." + m)))
    o.close()
    o.line()
    o.open("static inline void %s_register(vs_kernel *k, %s_s *s, %s v)" % (cn, cn, cn))
    if any(n for _, _, n in members(ct)):
        o.line("size_t i;")
    each(lambda m, mct: o.line(register_stmt("s->" + m, mct, "v." + m)))
    o.close()
    o.line()
    o.open("static inline size_t %s_leaves(%s_s *s, vs_sig **out)" % (cn, cn))
    o.line("size_t n = 0;")
    if any(n for _, _, n in members(ct)):
        o.line("size_t i;")
    each(lambda m, mct: o.line(leaves_stmt("s->" + m, mct)))
    o.line("return n;")
    o.close()
    o.line()
    o.open("static inline int %s_eq(%s a, %s b)" % (cn, cn, cn))
    if any(n for _, _, n in members(ct)):
        o.line("size_t i;")
    each(lambda m, mct: o.line("if (!%s) { return 0; }" % eq_expr("a." + m, "b." + m, mct)))
    o.line("return 1;")
    o.close()
    o.line()
    return o.text()


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
    return text + "#endif\n"
