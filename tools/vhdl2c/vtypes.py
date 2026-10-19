"""Mapping of the VHDL types to their C representation.

Values of the scalar types (std_logic, boolean, bit, std_logic_vector and its relatives of up to
64 bits) are held in a uint64_t ; integers in an int64_t ; enumerations in a uint32_t ordinal.
The 9-valued std_logic is reduced to two values : '1' and 'H' are 1, every other value is 0.
"""

import frontend
from pyGHDL.libghdl import files_map, name_table
from pyGHDL.libghdl.vhdl import nodes

K = nodes.Iir_Kind


class Unsupported(Exception):
    pass


def where(node):
    """'file:line' of a node, for the messages."""
    try:
        loc = nodes.Get_Location(node)
        fe = files_map.Location_To_File(loc)
        line = files_map.Location_File_To_Line(loc, fe)
        name = name_table.Get_Name_Ptr(files_map.Get_File_Name(fe))
        return "%s:%d" % (name.split("/")[-1], line)
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

    def __init__(self, width, asc=False, lo=0, hi=None, signed=False):
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

    def __init__(self, lo=None, hi=None):
        self.lo, self.hi = lo, hi

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


def const_int(expr):
    """Value of a static integer expression."""
    kind = nodes.Get_Kind(expr)
    if kind == K.Integer_Literal:
        return nodes.Get_Value(expr)
    if kind in (K.Simple_Name, K.Selected_Name):
        decl = nodes.Get_Named_Entity(expr)
        if nodes.Get_Kind(decl) == K.Constant_Declaration and nodes.Get_Default_Value(decl):
            return const_int(nodes.Get_Default_Value(decl))
        if nodes.Get_Kind(decl) == K.Enumeration_Literal:
            return nodes.Get_Enum_Pos(decl)
        raise unsupported(expr, "bound is not a static constant")
    if kind == K.Parenthesis_Expression:
        return const_int(nodes.Get_Expression(expr))
    binary = {
        K.Addition_Operator: lambda a, b: a + b,
        K.Substraction_Operator: lambda a, b: a - b,
        K.Multiplication_Operator: lambda a, b: a * b,
        K.Division_Operator: lambda a, b: int(a / b),
        K.Modulus_Operator: lambda a, b: a % b,
        K.Exponentiation_Operator: lambda a, b: a ** b,
    }
    if kind in binary:
        return binary[kind](const_int(nodes.Get_Left(expr)), const_int(nodes.Get_Right(expr)))
    if kind == K.Negation_Operator:
        return -const_int(nodes.Get_Operand(expr))
    if kind == K.Type_Conversion:
        return const_int(nodes.Get_Expression(expr))
    raise unsupported(expr, "bound is not a static integer")


def range_of(constraint):
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
    left = const_int(le)
    right = const_int(re_)
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
        return Int()
    if bkind == K.Array_Type_Definition:
        elem = nodes.Get_Element_Subtype(base)
        et = type_of(elem)
        width, asc, lo, hi = constraint_of(t)
        if et.kind == "bit":
            signed = type_name(base) == "signed"
            if width is not None and width > 64 * 8:
                raise unsupported(t, "vector wider than 512 bits")
            return Vec(width, asc, lo, hi, signed)
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
