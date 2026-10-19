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
    left = const_int(nodes.Get_Left_Limit_Expr(rng))
    right = const_int(nodes.Get_Right_Limit_Expr(rng))
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
        if et.kind == "bit":
            signed = type_name(base) == "signed"
            width, asc, lo, hi = constraint_of(t)
            return Vec(width, asc, lo, hi, signed)
        raise unsupported(t, "array of non-bit elements")
    raise unsupported(t, "type")


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
