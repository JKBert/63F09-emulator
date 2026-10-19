"""Counts the node kinds and the predefined functions used by the design.

usage: census.py <vhdl dir>
"""

import collections
import os
import sys

import frontend
from pyGHDL.libghdl.vhdl import nodes

if __name__ == "__main__":
    frontend.init()
    here = os.path.dirname(os.path.abspath(__file__))
    kinds = collections.Counter()
    predef = collections.Counter()
    for df in frontend.load_project(sys.argv[1], os.path.join(here, "sources.list")):
        for unit in frontend.units(df):
            for n in frontend.walk(unit):
                kinds[frontend.kind_name(n)] += 1
                if nodes.Get_Kind(n) in (nodes.Iir_Kind.Function_Call,) or "Operator" in frontend.kind_name(n):
                    impl = nodes.Get_Implementation(n)
                    if impl:
                        p = nodes.Get_Implicit_Definition(impl)
                        predef[nodes.Iir_Predefined(p).name] += 1
    print("== node kinds")
    for k, c in kinds.most_common():
        print("%7d %s" % (c, k))
    print("== predefined functions")
    for k, c in predef.most_common():
        print("%7d %s" % (c, k))
