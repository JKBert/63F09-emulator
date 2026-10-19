"""Mapping of the VHDL types to their C representation.

Values of the scalar types (std_logic, boolean, bit, std_logic_vector and its relatives of up to
64 bits) are held in a uint64_t ; integers in an int64_t ; enumerations in a uint32_t ordinal.
The 9-valued std_logic is reduced to two values : '1' and 'H' are 1, every other value is 0.
"""

import os

import frontend
from pyGHDL.libghdl import files_map, name_table
from pyGHDL.libghdl.vhdl import nodes

K = nodes.Iir_Kind


class Unsupported(Exception):
    pass


_file_cache = {}


def where(node):
    """'file:line' of a node, for the messages. The line is counted here : GHDL's own line lookup raises an
    exception that ends the process for some of its files."""
    try:
        loc = nodes.Get_Location(node)
        if not loc:
            return "node #%d" % node
        fe = files_map.Location_To_File(loc)
        if not fe:
            return "node #%d" % node
        pos = files_map.Location_File_To_Pos(loc, fe)
        d = name_table.Get_Name_Ptr(files_map.Get_Directory_Name(fe))
        f = name_table.Get_Name_Ptr(files_map.Get_File_Name(fe))
        path = os.path.join(d, f)
        if path not in _file_cache:
            _file_cache[path] = open(path, "rb").read()
        return "%s:%d" % (f.split("/")[-1], _file_cache[path].count(b"\n", 0, pos) + 1)
    except Exception:
        return "node #%d" % node


def unsupported(node, what):
    return Unsupported("%s : %s (%s)" % (where(node), what, frontend.kind_name(node)))


class CT:
    """Description of the C representation of a VHDL type."""
    kind = "?"


class Bit(CT):
    kind = "bit"
    width = 1
    signed = False

    def __repr__(self):
        return "Bit"


class Vec(CT):
    kind = "vec"

    def __init__(self, width, asc=False, lo=0, hi=None, signed=False, vtype=None):
        self.vtype = vtype          # 'unsigned' or 'signed' (numeric_std), None for std_logic_vector
        self.width = width
        self.asc = asc
        self.lo = lo
        self.hi = (lo + width - 1) if (hi is None and width is not None) else hi
        self.signed = signed

    def pos(self, index):
        """Bit position of the element with the given (constant) index."""
        return (self.hi - index) if self.asc else (index - self.lo)

    def __repr__(self):
        return "Vec(%s%s)" % (self.width, "s" if self.signed else "")


class Int(CT):
    kind = "int"
    width = 64
    signed = True

    def __init__(self, lo=None, hi=None, left=0):
        self.lo, self.hi = lo, hi
        self.left = left            # value of an object that has no initial value : 'left of the subtype

    def __repr__(self):
        return "Int"


class Enum(CT):
    kind = "enum"
    width = 32
    signed = False

    def __init__(self, decl, name, lits):
        self.decl, self.name, self.lits = decl, name, lits

    def __repr__(self):
        return "Enum(%s)" % self.name


class Rec(CT):
    """A record : a C structure of its fields."""
    kind = "rec"
    width = None

    def __init__(self, cname, fields):
        self.cname = cname
        self.fields = fields        # [(c field name, vhdl name, CT)]

    def __repr__(self):
        return "Rec(%s)" % self.cname


class Arr(CT):
    """An array of elements that are not bits : a C structure that holds a C array (so that it copies by value)."""
    kind = "arr"
    width = None

    def __init__(self, cname, elem, length, lo, hi, asc):
        self.cname = cname
        self.elem, self.length = elem, length
        self.lo, self.hi, self.asc = lo, hi, asc

    def pos(self, index):
        """Position in the C array of the element with the given (constant) index : the leftmost element is first."""
        return (index - self.lo) if self.asc else (self.hi - index)

    def __repr__(self):
        return "Arr(%s)" % self.cname


# The composite types met so far, in the order in which they must be defined, and their structural keys.
COMPOSITES = []
_by_key = {}
_names_used = {}


def new_cname(base):
    base = "".join(c if c.isalnum() or c == "_" else "_" for c in base.lower()) or "anon"
    n = _names_used.get(base, 0)
    _names_used[base] = n + 1
    return base if n == 0 else "%s_%d" % (base, n + 1)


def ct_key(ct):
    if ct.kind in ("rec", "arr"):
        return ("c", ct.cname)
    return (ct.kind, getattr(ct, "width", None), getattr(ct, "signed", None))


def is_wide(ct):
    return ct.kind == "vec" and ct.width is not None and ct.width > 64


def nwords(ct):
    return (ct.width + 63) // 64


def leaf_count(ct):
    """Number of vs_sig that make up a signal of this type."""
    if is_wide(ct):
        return nwords(ct)
    if ct.kind == "rec":
        return sum(leaf_count(f[2]) for f in ct.fields)
    if ct.kind == "arr":
        return ct.length * leaf_count(ct.elem)
    return 1


def ctype_val(ct):
    """C type of a value."""
    if is_wide(ct):
        return "vs_w"
    if ct.kind == "int":
        return "int64_t"
    if ct.kind == "enum":
        return "uint32_t"
    if ct.kind in ("rec", "arr"):
        return ct.cname
    return "uint64_t"


def ctype_sig(ct):
    """C type of the storage of a signal."""
    if is_wide(ct):
        return "vs_sigw%d" % nwords(ct)
    if ct.kind in ("rec", "arr"):
        return ct.cname + "_s"
    return "vs_sig"


BITLIKE = ("std_ulogic", "boolean", "bit")


def numeric_kind(t):
    """'signed' or 'unsigned' for the numeric_std vectors (whose base types are UNRESOLVED_SIGNED and
    UNRESOLVED_UNSIGNED), None for the others."""
    name = type_name(t)
    if name.endswith("unsigned"):
        return "unsigned"
    if name.endswith("signed"):
        return "signed"
    return None


def type_name(t):
    if not t:
        return ""
    if not frontend.has_field(nodes.Get_Kind(t), frontend.nodes_meta.fields.Type_Declarator):
        return ""
    d = nodes.Get_Type_Declarator(t)
    return frontend.ident(d) if d else ""


SUBTYPE_KINDS = (
    K.Enumeration_Subtype_Definition,
    K.Integer_Subtype_Definition,
    K.Array_Subtype_Definition,
    K.Floating_Subtype_Definition,
    K.Physical_Subtype_Definition,
    K.Record_Subtype_Definition,
)


def base_of(t):
    """Base type of a type or subtype node (subtypes lead to their parent type)."""
    while nodes.Get_Kind(t) in SUBTYPE_KINDS:
        parent = nodes.Get_Parent_Type(t)
        if not parent:
            break
        t = parent
    return t


# The value that stands for each generic of the entity being translated when a type bound depends on it : the
# upper bound of its declared range (NCPUS : 8), else its default value. The structures are sized for it.
STATIC_GENERICS = {}


class _Return(Exception):
    def __init__(self, value):
        self.value = value


def const_int(expr, env=None):
    """Value of a static integer or boolean expression. `env` maps declarations (the parameters and the variables of
    a function that is being interpreted) to their values."""
    env = env if env is not None else {}
    kind = nodes.Get_Kind(expr)
    if kind == K.Integer_Literal:
        return nodes.Get_Value(expr)
    if kind in (K.Simple_Name, K.Selected_Name):
        decl = nodes.Get_Named_Entity(expr)
        if decl in env:
            return env[decl]
        dk = nodes.Get_Kind(decl)
        if dk == K.Constant_Declaration and nodes.Get_Default_Value(decl):
            return const_int(nodes.Get_Default_Value(decl), env)
        if dk == K.Enumeration_Literal:
            return nodes.Get_Enum_Pos(decl)
        if dk == K.Interface_Constant_Declaration and decl in STATIC_GENERICS:
            return STATIC_GENERICS[decl]
        raise unsupported(expr, "bound is not a static constant")
    if kind == K.Parenthesis_Expression:
        return const_int(nodes.Get_Expression(expr), env)
    if kind == K.Type_Conversion or kind == K.Qualified_Expression:
        return const_int(nodes.Get_Expression(expr), env)
    binary = {
        K.Addition_Operator: lambda a, b: a + b,
        K.Substraction_Operator: lambda a, b: a - b,
        K.Multiplication_Operator: lambda a, b: a * b,
        K.Division_Operator: lambda a, b: int(a / b),
        K.Modulus_Operator: lambda a, b: a % b,
        K.Remainder_Operator: lambda a, b: int(a - b * int(a / b)),
        K.Exponentiation_Operator: lambda a, b: a ** b,
        K.Equality_Operator: lambda a, b: int(a == b),
        K.Inequality_Operator: lambda a, b: int(a != b),
        K.Less_Than_Operator: lambda a, b: int(a < b),
        K.Less_Than_Or_Equal_Operator: lambda a, b: int(a <= b),
        K.Greater_Than_Operator: lambda a, b: int(a > b),
        K.Greater_Than_Or_Equal_Operator: lambda a, b: int(a >= b),
        K.And_Operator: lambda a, b: int(bool(a) and bool(b)),
        K.Or_Operator: lambda a, b: int(bool(a) or bool(b)),
        K.Xor_Operator: lambda a, b: int(bool(a) != bool(b)),
    }
    if kind in binary:
        return binary[kind](const_int(nodes.Get_Left(expr), env), const_int(nodes.Get_Right(expr), env))
    if kind == K.Negation_Operator:
        return -const_int(nodes.Get_Operand(expr), env)
    if kind == K.Absolute_Operator:
        return abs(const_int(nodes.Get_Operand(expr), env))
    if kind == K.Not_Operator:
        return int(not const_int(nodes.Get_Operand(expr), env))
    if kind == K.Function_Call:
        return _call(expr, env)
    raise unsupported(expr, "bound is not a static integer")


def _call(expr, env):
    """A call of a function in a constant expression : the function is interpreted."""
    impl = nodes.Get_Implementation(expr)
    if nodes.Get_Implicit_Definition(impl) != nodes.Iir_Predefined.PNone:
        raise unsupported(expr, "predefined function in a bound")
    body = nodes.Get_Subprogram_Body(impl)
    if not body:
        raise unsupported(expr, "function without a body in a bound")
    formals = []
    p = nodes.Get_Interface_Declaration_Chain(impl)
    while p:
        formals.append(p)
        p = nodes.Get_Chain(p)
    local = {}
    a = nodes.Get_Parameter_Association_Chain(expr)
    for i, p in enumerate(formals):
        if not a:
            raise unsupported(expr, "missing argument")
        local[p] = const_int(nodes.Get_Actual(a), env)
        a = nodes.Get_Chain(a)
    spec = nodes.Get_Subprogram_Specification(body)
    if spec and spec != impl:
        q = nodes.Get_Interface_Declaration_Chain(spec)
        for p in formals:
            local[q] = local[p]
            q = nodes.Get_Chain(q)
    d = nodes.Get_Declaration_Chain(body)
    while d:
        if nodes.Get_Kind(d) == K.Variable_Declaration:
            init = nodes.Get_Default_Value(d)
            local[d] = const_int(init, local) if init else 0
        d = nodes.Get_Chain(d)
    try:
        _run(nodes.Get_Sequential_Statement_Chain(body), local)
    except _Return as r:
        return r.value
    raise unsupported(expr, "function that does not return")


def _run(chain, env):
    s = chain
    while s:
        k = nodes.Get_Kind(s)
        if k == K.Variable_Assignment_Statement:
            t = nodes.Get_Target(s)
            if nodes.Get_Kind(t) not in (K.Simple_Name,):
                raise unsupported(s, "assignment in a constant function")
            env[nodes.Get_Named_Entity(t)] = const_int(nodes.Get_Expression(s), env)
        elif k == K.If_Statement:
            if const_int(nodes.Get_Condition(s), env):
                _run(nodes.Get_Sequential_Statement_Chain(s), env)
            else:
                e = nodes.Get_Else_Clause(s)
                while e:
                    c = nodes.Get_Condition(e)
                    if c is None or not c or const_int(c, env):
                        _run(nodes.Get_Sequential_Statement_Chain(e), env)
                        break
                    e = nodes.Get_Else_Clause(e)
        elif k == K.While_Loop_Statement:
            c = nodes.Get_Condition(s)
            n = 0
            while (not c) or const_int(c, env):
                _run(nodes.Get_Sequential_Statement_Chain(s), env)
                n += 1
                if n > 100000:
                    raise unsupported(s, "loop that does not end")
        elif k == K.For_Loop_Statement:
            spec = nodes.Get_Parameter_Specification(s)
            left, right, asc = range_of(spec if nodes.Get_Discrete_Range(spec) == 0 and False else (nodes.Get_Discrete_Range(spec) or nodes.Get_Subtype_Indication(spec)), env)
            rng = range(left, right + 1) if asc else range(left, right - 1, -1)
            for i in rng:
                env[spec] = i
                _run(nodes.Get_Sequential_Statement_Chain(s), env)
        elif k == K.Return_Statement:
            raise _Return(const_int(nodes.Get_Expression(s), env))
        elif k == K.Null_Statement:
            pass
        else:
            raise unsupported(s, "statement in a constant function")
        s = nodes.Get_Chain(s)


def range_of(constraint, env=None):
    """(left, right, ascending) of the range of an index constraint node."""
    rng = constraint
    kind = nodes.Get_Kind(rng)
    if kind in (K.Integer_Subtype_Definition, K.Enumeration_Subtype_Definition):
        rng = nodes.Get_Range_Constraint(rng)
        kind = nodes.Get_Kind(rng)
    if kind != K.Range_Expression:
        raise unsupported(constraint, "dynamic index range")
    le, re_ = nodes.Get_Left_Limit_Expr(rng), nodes.Get_Right_Limit_Expr(rng)
    if not le or not re_:
        raise unsupported(constraint, "range without explicit limits")
    left = const_int(le, env)
    right = const_int(re_, env)
    asc = nodes.Get_Direction(rng) == nodes.DirectionType.To
    return left, right, asc


def type_of(t):
    """CT of a type or subtype node."""
    kind = nodes.Get_Kind(t)
    base = base_of(t)
    bkind = nodes.Get_Kind(base)
    if bkind == K.Enumeration_Type_Definition:
        name = type_name(base)
        if name in BITLIKE:
            return Bit()
        lits = []
        for lit in frontend.list_elements_flist(nodes.Get_Enumeration_Literal_List(base)):
            lits.append(frontend.ident(lit))
        return Enum(base, name, lits)
    if bkind in (K.Integer_Type_Definition, K.Integer_Subtype_Definition):
        if kind == K.Integer_Subtype_Definition:
            try:
                left, right, asc = range_of(t)
                return Int(min(left, right), max(left, right), left)
            except Unsupported:
                pass
        return Int()
    if bkind == K.Array_Type_Definition:
        elem = nodes.Get_Element_Subtype(base)
        et = type_of(elem)
        if et.kind == "vec" and et.width is None:
            # VHDL-2008 : the constraint of the elements comes with the constraint of the array
            node = t
            while node and nodes.Get_Kind(node) == K.Array_Subtype_Definition:
                ec = nodes.Get_Array_Element_Constraint(node) if frontend.has_field(nodes.Get_Kind(node), frontend.nodes_meta.fields.Array_Element_Constraint) else 0
                if ec:
                    et = type_of(ec)
                    break
                node = nodes.Get_Parent_Type(node)
        width, asc, lo, hi = constraint_of(t)
        if et.kind == "bit":
            signed = numeric_kind(base) == "signed"
            if width is not None and width > 64 * 8:
                raise unsupported(t, "vector wider than 512 bits")
            return Vec(width, asc, lo, hi, signed, numeric_kind(base))
        if width is None:
            raise unsupported(t, "unconstrained array")
        key = ("arr", ct_key(et), width, lo, hi, asc)
        if key not in _by_key:
            _by_key[key] = Arr(new_cname(type_name(t) or type_name(base) or "array"), et, width, lo, hi, asc)
            COMPOSITES.append(_by_key[key])
        return _by_key[key]
    if bkind == K.Record_Type_Definition:
        key = ("rec", base)
        if key not in _by_key:
            fields = []
            for el in frontend.list_elements_flist(nodes.Get_Elements_Declaration_List(base)):
                fields.append((cid_field(frontend.ident(el)), frontend.ident(el), type_of(nodes.Get_Type(el))))
            _by_key[key] = Rec(new_cname(type_name(base) or "record"), fields)
            COMPOSITES.append(_by_key[key])
        return _by_key[key]
    raise unsupported(t, "type")


def cid_field(name):
    return "f_" + name.lower()


def constraint_of(t):
    """(width, ascending, low index, high index) of a constrained vector subtype ; width None when unconstrained."""
    node = t
    while node:
        kind = nodes.Get_Kind(node)
        if kind == K.Array_Subtype_Definition:
            lst = nodes.Get_Index_Constraint_List(node)
            if lst and lst > 2:
                from pyGHDL.libghdl.vhdl import flists
                first = flists.Get_Nth_Element(lst, 0)
                left, right, asc = range_of(first)
                lo, hi = (left, right) if asc else (right, left)
                return hi - lo + 1, asc, lo, hi
            # Without constraint of its own : follow the type mark.
            mark = nodes.Get_Subtype_Type_Mark(node) if frontend.has_field(kind, frontend.nodes_meta.fields.Subtype_Type_Mark) else 0
            if not mark:
                break
            decl = nodes.Get_Named_Entity(mark)
            node = nodes.Get_Type(decl) if decl else 0
            continue
        break
    return None, False, 0, None
