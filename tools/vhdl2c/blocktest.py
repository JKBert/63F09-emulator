"""Block tests : the C generated for an entity is compared to GHDL on random stimuli.

For each block the test builds, from the entity's ports, a VHDL test bench and a C test bench
that read the same stimulus file, apply it phase by phase (clocks low, then clocks high), and
print every output after each phase. The two outputs must be identical.

usage: blocktest.py <vhdl dir> <ghdl binary> [block ...]
"""

import glob
import os
import random
import shutil
import subprocess
import sys
import tempfile

import frontend
from pyGHDL.libghdl.vhdl import nodes

K = nodes.Iir_Kind

# The opcodes of the 6809 : the others raise the trap interrupt, which this design stops with "finish" ; a program
# made of random bytes would stop at once.
ILLEGAL_6809 = {0x01, 0x02, 0x05, 0x0B, 0x14, 0x15, 0x18, 0x1B, 0x38, 0x3E, 0x41, 0x42, 0x45, 0x4B, 0x4E, 0x51, 0x52,
                0x55, 0x5B, 0x5E, 0x61, 0x62, 0x65, 0x6B, 0x71, 0x72, 0x75, 0x7B, 0x87, 0x8F, 0xC7, 0xCD, 0xCF}
LEGAL_6809 = [op for op in range(256) if op not in ILLEGAL_6809 and op not in (0x10, 0x11)]

# Per block : clocks (toggled every cycle), resets (asserted at the start and now and then, the
# value is the active level), warm-up cycles ignored in the comparison, number of cycles, and the
# probability that an input changes from one cycle to the next.
BLOCKS = {
    "clk_63f75": dict(clocks=["tick"], resets={"reset_n": 0}, warm=2, cycles=600, change=0.3),
    "lzc_4": dict(clocks=[], resets={}, warm=0, cycles=300, change=0.5),
    "lzc_8": dict(clocks=[], resets={}, warm=0, cycles=600, change=0.5),
    "lzc_16": dict(clocks=[], resets={}, warm=0, cycles=1000, change=0.5),
    "lzc_32": dict(clocks=[], resets={}, warm=0, cycles=1500, change=0.5),
    "lzc_64": dict(clocks=[], resets={}, warm=0, cycles=2500, change=0.5),
    "amc_63f42": dict(clocks=["e_int", "q_int"], resets={"reset_n": 0}, warm=0, cycles=600, change=0.4),
    "lzc_128": dict(clocks=[], resets={}, warm=0, cycles=2500, change=0.5, trace=False),
    "lzc_256": dict(clocks=[], resets={}, warm=0, cycles=2500, change=0.5, trace=False),
    "fp_cmp": dict(clocks=[], resets={}, warm=0, cycles=3000, change=0.6),
    "fp_max": dict(clocks=[], resets={}, warm=0, cycles=3000, change=0.6),
    "fp_mac": dict(clocks=[], resets={}, warm=0, cycles=3000, change=0.6),
    "fp_ext": dict(clocks=[], resets={}, warm=0, cycles=3000, change=0.6),
    "fp_rnd": dict(clocks=[], resets={}, warm=0, cycles=3000, change=0.6, int_range=(0, 2200)),
    "fp_cvt": dict(clocks=["clock"], resets={}, warm=1, cycles=3000, change=0.5, ones=("ce",)),
    "fp_fma": dict(clocks=["clock"], resets={"reset": 0}, warm=1, cycles=3000, change=0.5, ones=("ce",)),
    "fp_fdiv": dict(clocks=["clock"], resets={"reset": 0}, warm=1, cycles=3000, change=0.5, ones=("ce",)),
    "fp_exe": dict(clocks=["clock"], resets={"reset": 0}, warm=1, cycles=3000, change=0.5, ones=("ce",)),
    "fp_unit": dict(clocks=["clock"], resets={"reset": 0}, warm=1, cycles=3000, change=0.5, ones=("ce",)),
    "fp_sgnj": dict(clocks=[], resets={}, warm=0, cycles=1500, change=0.6, trace=False),
    "cpu_63f09": dict(clocks=["extal"], resets={"reset_n": 0}, warm=2, cycles=6000, change=0.5,
                      ones=("nmi_n", "firq_n", "irq_n", "mrdy", "dma_breq_n", "halt_n", "eirq_n", "pagefault_n", "lock_granted"),
                      choices={"d_in": LEGAL_6809}),
    "mmu_63f29": dict(clocks=["extal"], resets={"reset_n": 0}, warm=2, cycles=6000, change=0.5, generics={"mmu": 1},
                      ones=("nmi_n", "firq_n", "irq_n", "mrdy", "dma_breq_n", "halt_n", "eirq_n", "lock_granted"),
                      choices={"d_in": LEGAL_6809}),
    # a directed test of the transmitter : the ACIA is set up (divisor 13, 8N1, /16) and sends 0x4F
    "acia_tx": dict(entity="acia_63f50", clocks=["e", "sysclk"], resets={"rst_n": 0}, warm=3, cycles=12000, change=0,
                    initial={"rxd": 1, "rw_n": 1},
                    script=[(10, {"cs": 1, "addr": 0, "rw_n": 0, "d_in": 3}), (12, {"cs": 0, "rw_n": 1}),
                            (14, {"cs": 1, "addr": 2, "rw_n": 0, "d_in": 0}), (16, {"cs": 0, "rw_n": 1}),
                            (18, {"cs": 1, "addr": 3, "rw_n": 0, "d_in": 13}), (20, {"cs": 0, "rw_n": 1}),
                            (22, {"cs": 1, "addr": 0, "rw_n": 0, "d_in": 0x15}), (24, {"cs": 0, "rw_n": 1}),
                            (30, {"cs": 1, "addr": 1, "rw_n": 0, "d_in": 0x4F}), (32, {"cs": 0, "rw_n": 1}),
                            (300, {"cs": 1, "rw_n": 0, "d_in": 0x4B}), (302, {"cs": 0, "rw_n": 1}),
                            (3000, {"cs": 1, "rw_n": 0, "d_in": 0x0A}), (3002, {"cs": 0, "rw_n": 1}),
                            (6000, {"cs": 1, "rw_n": 1}), (6002, {"cs": 0}), (7000, {"cs": 1, "addr": 0, "rw_n": 1}), (7002, {"cs": 0})]),
    "acia_63f50": dict(clocks=["e", "sysclk"], resets={"rst_n": 0}, warm=3, cycles=4000, change=0.15),
    "wdg_63f46": dict(clocks=["e", "sysclk"], resets={"rst_n": 0}, warm=3, cycles=3000, change=0.2),
}


def generic_defaults(entity, overrides=None):
    """[(name, value as a C integer, is boolean)] of the generics of the entity : the default values, unless
    `overrides` (a dict name -> value) gives another one."""
    from vtypes import const_int
    out = []
    g = nodes.Get_Generic_Chain(entity)
    while g:
        dv = nodes.Get_Default_Value(g)
        name = frontend.ident(g)
        v = const_int(dv) if dv else 0
        if overrides and name.lower() in overrides:
            v = int(overrides[name.lower()])
        from vtypes import type_name, base_of
        is_bool = type_name(base_of(nodes.Get_Type(g))).lower() == "boolean"
        out.append((name, v, is_bool))
        g = nodes.Get_Chain(g)
    return out


def port_info(entity):
    from vtypes import type_of
    ports = []
    p = nodes.Get_Port_Chain(entity)
    while p:
        ct = type_of(nodes.Get_Type(p))
        ports.append((frontend.ident(p), ct, nodes.Get_Mode(p)))
        p = nodes.Get_Chain(p)
    return ports


def qualified_type_name(t):
    """library.package.type of a named type, as VHDL text."""
    from vtypes import SUBTYPE_KINDS
    node = t
    while node:
        d = nodes.Get_Type_Declarator(node) if frontend.has_field(nodes.Get_Kind(node), frontend.nodes_meta.fields.Type_Declarator) else 0
        if d:
            parent = nodes.Get_Parent(d)
            if parent and nodes.Get_Kind(parent) == K.Package_Declaration:
                unit = nodes.Get_Parent(parent)
                lib = nodes.Get_Library(nodes.Get_Parent(unit))
                return "%s.%s.%s" % (frontend.ident(lib), frontend.ident(parent), frontend.ident(d))
            return frontend.ident(d)
        if nodes.Get_Kind(node) in SUBTYPE_KINDS:
            node = nodes.Get_Parent_Type(node)
        else:
            break
    raise ValueError("a port has an anonymous composite type")


def port_type_texts(entity):
    from vtypes import type_of
    out = {}
    p = nodes.Get_Port_Chain(entity)
    while p:
        t = nodes.Get_Type(p)
        ct = type_of(t)
        if ct.kind == "bit":
            out[frontend.ident(p)] = "std_logic"
        elif ct.kind == "vec":
            out[frontend.ident(p)] = "std_logic_vector(%d downto 0)" % (ct.width - 1)
        elif ct.kind == "int":
            out[frontend.ident(p)] = "integer"
        else:
            out[frontend.ident(p)] = qualified_type_name(t)
        p = nodes.Get_Chain(p)
    return out


class Leaf:
    """One scalar object of a port : a bit or vector, an integer, or an enumeration."""

    def __init__(self, name, vpath, cpath, ct, is_input):
        self.name = name        # for variables : unique, usable in an identifier
        self.vpath = vpath      # VHDL object name
        self.cpath = cpath      # C lvalue of the vs_sig (or of the array of words)
        self.ct = ct
        self.is_input = is_input


def leaves(ct, name, vpath, cpath, is_input):
    if ct.kind == "rec":
        for cname, vname, fct in ct.fields:
            yield from leaves(fct, name + "_" + vname, "%s.%s" % (vpath, vname), "%s.%s" % (cpath, cname), is_input)
    elif ct.kind == "arr":
        for i in range(ct.length):
            idx = ct.lo + i if ct.asc else ct.hi - i
            yield from leaves(ct.elem, "%s_%d" % (name, i), "%s(%d)" % (vpath, idx), "%s.a[%d]" % (cpath, i), is_input)
    else:
        yield Leaf(name, vpath, cpath, ct, is_input)


def port_leaves(ports, clocks):
    """Leaves of the non-clock inputs, and of the outputs, in port order."""
    ins, outs = [], []
    for n, ct, m in ports:
        is_in = m == nodes.Iir_Mode.In_Mode
        for lf in leaves(ct, n, n, "p_" + n, is_in):
            if is_in and n.lower() not in clocks:
                ins.append(lf)
            elif not is_in:
                outs.append(lf)
    return ins, outs


def vtype_name(ct, lib):
    """VHDL type of a port, for the signal declarations of the bench."""
    if ct.kind == "bit":
        return "std_logic"
    if ct.kind == "vec":
        return "std_logic_vector(%d downto 0)" % (ct.width - 1)
    raise ValueError("no name for %r" % ct)


def vhdl_bench(name, ports, cfg, lib="work", port_types=None, generics=()):
    clocks = [c.lower() for c in cfg["clocks"]]
    ins, outs = port_leaves(ports, clocks)
    o = []
    o.append("library ieee;\nuse ieee.std_logic_1164.all;\nuse ieee.numeric_std.all;\nuse std.textio.all;\n")
    libs = {lib} | {t.split(".")[0] for t in (port_types or {}).values() if t.count(".") == 2}
    for l in sorted(libs - {"work"}):
        o.append("library %s;\n" % l)
    o.append("entity tb is\nend entity tb;\n")
    o.append("architecture sim of tb is")
    for n, ct, m in ports:
        t = port_types[n]
        init = ""
        if m == nodes.Iir_Mode.In_Mode:
            init = " := '0'" if ct.kind == "bit" else (" := (others => '0')" if ct.kind == "vec" else "")
        o.append("    signal %s : %s%s;" % (n, t, init))
    o.append("begin")
    gmap = ""
    if generics:
        gmap = "generic map (%s) " % ", ".join("%s => %s" % (n, ("true" if v else "false") if b else v) for n, v, b in generics)
    o.append("    DUT : entity %s.%s %sport map (%s);" % (lib, name, gmap, ", ".join("%s => %s" % (n, n) for n, ct, m in ports)))
    o.append("    process")
    o.append('        file stim : text open read_mode is "stim.txt";')
    o.append('        file result : text open write_mode is "ghdl.out";')
    o.append("        variable l : line;")
    for lf in ins:
        if lf.ct.kind in ("bit", "vec"):
            o.append("        variable v_%s : std_logic_vector(%d downto 0);" % (lf.name, (lf.ct.width or 1) - 1))
        elif lf.ct.kind == "int":
            o.append("        variable v_%s : integer;" % lf.name)
    o.append("        procedure dump is")
    o.append("            variable o : line;")
    o.append("        begin")
    for lf in outs:
        if lf.ct.kind in ("bit", "vec"):
            ex = "std_logic_vector(%s)" % lf.vpath if getattr(lf.ct, "vtype", None) else lf.vpath
            o.append("            write(o, to_string(to_x01(%s)) & \" \");" % ex)
        elif lf.ct.kind == "int":
            o.append("            write(o, integer'image(%s) & \" \");" % lf.vpath)
        else:
            o.append("            write(o, %s'subtype'image(%s) & \" \");" % (lf.vpath, lf.vpath))
    o.append("            writeline(result, o);")
    o.append("        end procedure;")
    o.append("    begin")
    o.append("        wait for 1 ns;")
    o.append("        while not endfile(stim) loop")
    o.append("            readline(stim, l);")
    for lf in ins:
        if lf.ct.kind in ("bit", "vec", "int"):
            o.append("            read(l, v_%s);" % lf.name)
    for lf in ins:
        if lf.ct.kind in ("bit", "vec"):
            src = "v_%s(0)" % lf.name if lf.ct.kind == "bit" else "v_" + lf.name
            if getattr(lf.ct, "vtype", None):
                src = "%s(%s)" % (lf.ct.vtype, src)
            o.append("            %s <= %s;" % (lf.vpath, src))
        elif lf.ct.kind == "int":
            o.append("            %s <= v_%s;" % (lf.vpath, lf.name))
    for c in clocks:
        o.append("            %s <= '0';" % c)
    o.append("            wait for 5 ns;\n            dump;")
    for c in clocks:
        o.append("            %s <= '1';" % c)
    o.append("            wait for 5 ns;\n            dump;")
    o.append("        end loop;")
    o.append("        wait;")
    o.append("    end process;")
    o.append("end architecture sim;")
    return "\n".join(o) + "\n"


def c_width(ct):
    return ct.width if ct.kind in ("bit", "vec") else 0


def c_bench(name, ports, cfg, generics=()):
    from vtypes import ctype_sig, is_wide, nwords
    clocks = [c.lower() for c in cfg["clocks"]]
    ins, outs = port_leaves(ports, clocks)
    o = []
    o.append('#include <stdio.h>\n#include <string.h>\n\n#include "%s.h"\n' % name)
    o.append("static uint64_t bits(const char *s, size_t w)\n{\n    uint64_t v = 0;\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        v = (v << 1) | (s[i] == '1' || s[i] == 'H');\n    }\n    return v;\n}\n")
    o.append("static vs_w wbits(const char *s, size_t w)\n{\n    vs_w v = vs_w_zero();\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        v = vs_w_shl(v, 1, 64 * VS_WIDE_WORDS);\n        v.w[0] |= (s[i] == '1' || s[i] == 'H');\n    }\n    return v;\n}\n")
    o.append("static void put(const vs_sig *s, size_t w)\n{\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        putchar(((s->cur >> (w - 1 - i)) & 1) ? '1' : '0');\n    }\n    putchar(' ');\n}\n")
    o.append("static void putw(const vs_sig *s, size_t w)\n{\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        size_t b = w - 1 - i;\n        putchar(((s[b / 64].cur >> (b % 64)) & 1) ? '1' : '0');\n    }\n    putchar(' ');\n}\n")
    o.append("int main(int argc, char **argv)\n{")
    o.append("    vs_kernel k;\n    %s dut;\n    char line[65536];\n    FILE *f, *trace = NULL;\n    long phase = 0;\n" % name)
    for n, ct, m in ports:
        o.append("    %s p_%s;" % (ctype_sig(ct), n))
    o.append("")
    o.append("    if (argc < 2 || (f = fopen(argv[1], \"r\")) == NULL)\n    {\n        return 2;\n    }")
    o.append("    if (argc > 2)\n    {\n        trace = fopen(argv[2], \"w\");\n    }")
    o.append("    vs_kernel_init(&k);")
    for n, ct, m in ports:
        if ct.kind in ("rec", "arr"):
            o.append("    %s_register(&k, &p_%s, %s_zero());" % (ct.cname, n, ct.cname))
        elif is_wide(ct):
            o.append("    vs_w_register(&k, p_%s.w, %d, vs_w_zero());" % (n, nwords(ct)))
        else:
            o.append("    vs_register_signal(&k, &p_%s, 0);" % n)
            o.append('    vs_name(&k, &p_%s, NULL, "%s", %d);' % (n, n, ct.width))
    o.append('    %s_create(&k, &dut, "dut", %s);' % (name, ", ".join(["%dLL" % g[1] for g in generics] + ["&p_%s" % n for n, ct, m in ports])))
    o.append("    vs_settle(&k);")
    o.append("    while (fgets(line, sizeof(line), f) != NULL)\n    {\n        char *tok;")
    first = True
    for lf in ins:
        o.append("        tok = %s;" % ("strtok(line, \" \\n\")" if first else "strtok(NULL, \" \\n\")"))
        first = False
        if lf.ct.kind == "int":
            o.append("        vs_drive(&%s, (uint64_t) atoll(tok));" % lf.cpath)
        elif is_wide(lf.ct):
            o.append("        vs_w_drive(%s.w, %d, wbits(tok, %d));" % (lf.cpath, nwords(lf.ct), lf.ct.width))
        else:
            o.append("        vs_drive(&%s, bits(tok, %d));" % (lf.cpath, lf.ct.width))
    for phase in (0, 1):
        for c in clocks:
            o.append("        vs_drive(&p_%s, %d);" % (c, phase))
        o.append("        vs_settle(&k);")
        o.append("        if (vs_finished)\n        {\n            break;     /* the VHDL stopped the simulation (finish) */\n        }")
        for lf in outs:
            if lf.ct.kind == "int":
                o.append('        printf("%%lld ", (long long) (int64_t) %s.cur);' % lf.cpath)
            elif lf.ct.kind == "enum":
                names = ", ".join('"%s"' % x for x in lf.ct.lits)
                o.append("        { static const char *const lits[] = { %s }; printf(\"%%s \", lits[%s.cur]); }" % (names, lf.cpath))
            elif is_wide(lf.ct):
                o.append("        putw(%s.w, %d);" % (lf.cpath, lf.ct.width))
            else:
                o.append("        put(&%s, %d);" % (lf.cpath, lf.ct.width))
        o.append("        putchar('\\n');")
        o.append("        if (trace != NULL)\n        {\n            vs_dump(&k, trace, phase);\n        }\n        phase++;")
    o.append("    }\n    if (trace != NULL)\n    {\n        fclose(trace);\n    }\n    fclose(f);\n    vs_kernel_free(&k);\n    return 0;\n}")
    return "\n".join(o) + "\n"


def stimulus(ports, cfg, seed):
    rnd = random.Random(seed)
    clocks = [c.lower() for c in cfg["clocks"]]
    ins, outs = port_leaves(ports, clocks)
    resets = {k.lower(): v for k, v in cfg["resets"].items()}

    def fresh(lf):
        """A random value, biased towards the edge cases : zero, all ones, one bit, few significant bits."""
        if lf.ct.kind == "int":
            lo = lf.ct.lo if lf.ct.lo is not None else 0
            hi = lf.ct.hi if lf.ct.hi is not None else 15
            ilo, ihi = cfg.get("int_range", (-1000, 1000))
            return rnd.randint(max(lo, ilo), min(hi, ihi))
        w = lf.ct.width
        choices = cfg.get("choices", {}).get(lf.name.lower())
        if choices and rnd.random() < 0.9:
            return rnd.choice(choices)
        mode = rnd.randrange(8)
        if mode == 0:
            return 0
        if mode == 1:
            return (1 << w) - 1
        if mode == 2:
            return 1 << rnd.randrange(w)
        if mode in (3, 4):
            return rnd.getrandbits(w) >> rnd.randrange(w)
        if mode == 5:
            return (rnd.getrandbits(w) << rnd.randrange(w)) & ((1 << w) - 1)
        return rnd.getrandbits(w)

    cur = {lf.name: fresh(lf) for lf in ins}
    script = cfg.get("script")
    if script:
        # directed test : the inputs hold their values, except at the samples where the script changes them
        cur = {lf.name: cfg.get("initial", {}).get(lf.name.lower(), 0) for lf in ins}
        events = {}
        for at, changes in script:
            events.setdefault(at, {}).update(changes)
    lines = []
    reset_left = 3
    for sample in range(cfg["cycles"]):
        if script:
            for n, v in events.get(sample, {}).items():
                for lf in ins:
                    if lf.name.lower() == n:
                        cur[lf.name] = v
        if reset_left == 0 and rnd.random() < 0.01 and not script:
            reset_left = rnd.randint(1, 3)
        row = []
        for lf in ins:
            if lf.name.lower() in resets:
                active = resets[lf.name.lower()]
                v = active if reset_left else 1 - active
            else:
                if not script and rnd.random() < cfg["change"]:
                    cur[lf.name] = fresh(lf)
                    if lf.name.lower() in cfg.get("ones", ()) and rnd.random() < 0.9:
                        cur[lf.name] = (1 << (lf.ct.width or 1)) - 1 if lf.ct.kind != "int" else 1
                v = cur[lf.name]
            row.append(str(v) if lf.ct.kind == "int" else format(v, "0%db" % lf.ct.width))
        if reset_left:
            reset_left -= 1
        lines.append(" ".join(row))
    return "\n".join(lines) + "\n"


def run(cmd, cwd, quiet=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0 and not quiet:
        sys.stdout.write("   command failed: %s\n%s%s\n" % (" ".join(cmd), r.stdout[-1500:], r.stderr[-1500:]))
    return r.returncode == 0


STD = ["--std=08", "-frelaxed", "-fsynopsys"]


def analyse_project(ghdl, files, shared):
    for lib, path in files:
        if not run([ghdl, "-a"] + STD + ["--work=" + lib, "--workdir=" + shared, path], shared):
            return False
    return True


class TraceUnavailable(str):
    """GHDL could not write the trace : the internal signals are not compared."""


def trace_diff(ghdl, shared, work, tb, wd, pp, skip):
    """Reruns both sides with every named signal traced, and reports the first diverging signals."""
    import vcdcmp
    vcd = os.path.join(work, "dump.vcd")
    r = subprocess.run([ghdl, "--elab-run"] + STD + [wd, pp, tb, "--vcd=" + vcd], cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        return TraceUnavailable((r.stdout + r.stderr).strip()[-200:])
    run(["./tb_c", "stim.txt", "c.trace"], work, quiet=True)
    r = vcdcmp.compare(vcd, os.path.join(work, "c.trace"), skip_phases=skip)
    if r is None:
        return None
    phase, diffs = r
    out = ["   first internal difference at phase %d (cycle %d, clocks %s) :" % (phase, phase // 2, "low" if phase % 2 == 0 else "high")]
    out += ["      %-40s ghdl=%s c=%s" % d for d in diffs]
    return "\n".join(out)


def run_block(name, cfg, ports, ghdl, shared, root, lib="work", generics=(), port_types=None):
    with tempfile.TemporaryDirectory() as work:
        open(os.path.join(work, "tb.c"), "w").write(c_bench(name, ports, cfg, generics))
        open(os.path.join(work, "stim.txt"), "w").write(stimulus(ports, cfg, 7))
        tb = "tb_" + name
        vhd = os.path.join(shared, tb + ".vhd")
        open(vhd, "w").write(vhdl_bench(name, ports, cfg, lib, port_types, generics).replace("entity tb ", "entity %s " % tb).replace("entity tb is", "entity %s is" % tb)
                             .replace("architecture sim of tb is", "architecture sim of %s is" % tb).replace("end entity tb;", "end entity %s;" % tb))
        wd = "--workdir=" + shared
        pp = "-P" + shared
        ok = run([ghdl, "-a"] + STD + [wd, pp, vhd], shared) and run([ghdl, "--elab-run"] + STD + [wd, pp, tb], work)
        src = os.path.join(root, "src")
        ok = ok and run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra", "-I" + os.path.join(src, "rt"),
                         "-I" + os.path.join(src, "gen"), "-I" + src, "-o", "tb_c", "tb.c"]
                        + sorted(glob.glob(os.path.join(src, "gen", "*.c"))) + sorted(glob.glob(os.path.join(src, "hand", "*.c")))
                        + [os.path.join(src, "rt", "vsim.c")], work)
        if not ok:
            return "FAILED to build or run"
        out = subprocess.run(["./tb_c", "stim.txt"], cwd=work, capture_output=True, text=True).stdout
        keep = os.environ.get("BLOCKTEST_KEEP")
        if keep:
            if keep in ("1", "yes", "true"):
                keep = os.path.join(root, "build", "blocktest-keep")      # a flag, not a directory name
            os.makedirs(keep, exist_ok=True)
            open(os.path.join(keep, name + ".c.out"), "w").write(out)
            for f in ("ghdl.out", "stim.txt", "tb.c"):
                shutil.copy(os.path.join(work, f), os.path.join(keep, name + "." + f))
        skip = 2 * cfg["warm"]
        a = [x.strip().lower() for x in open(os.path.join(work, "ghdl.out")).read().split("\n")][skip:]
        b = [x.strip().lower() for x in out.split("\n")][skip:]
        def same(x, y):
            """Equal, except that a bit that GHDL reports as 'X' (a 'U' signal, never assigned) matches anything."""
            return len(x) == len(y) and all(p == q or p == "x" for p, q in zip(x, y))

        if len(a) == len(b) and all(same(x, y) for x, y in zip(a, b)):
            internal = trace_diff(ghdl, shared, work, tb, wd, pp, skip) if cfg.get("trace", True) else None
            if isinstance(internal, TraceUnavailable):
                return "OK (%d samples identical, %d distinct output values ; internal signals NOT compared : GHDL cannot write the trace)" % (len([x for x in a if x]), len(set(a)))
            if internal:
                return "MISMATCH of the internal signals (the outputs are identical)\n" + internal
            return "OK (%d samples identical, %d distinct output values, all named signals compared)" % (len([x for x in a if x]), len(set(a)))
        for i, (x, y) in enumerate(zip(a, b)):
            if not same(x, y):
                return "MISMATCH at sample %d\n   ghdl: %s\n   c   : %s\n%s" % (i + skip, x, y, trace_diff(ghdl, shared, work, tb, wd, pp, skip) or "   (the internal signals do not differ)")
        return "MISMATCH (different lengths %d / %d)" % (len(a), len(b))


def main(argv):
    vhdl_dir, ghdl = argv[1], argv[2]
    names = argv[3:] or list(BLOCKS)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    here = os.path.dirname(os.path.abspath(__file__))
    listing = os.path.join(here, "sources.list")
    frontend.init()
    files = frontend.project_files(vhdl_dir, listing)
    dfs = frontend.analyze_files(files)
    entities = {}
    libs = {}
    for df, (lib, path) in zip(dfs, files):
        for unit in frontend.units(df):
            lu = nodes.Get_Library_Unit(unit)
            if nodes.Get_Kind(lu) == K.Entity_Declaration:
                entities[frontend.ident(lu).lower()] = lu
                libs[frontend.ident(lu).lower()] = lib
    failures = 0
    with tempfile.TemporaryDirectory() as shared:
        import zeroinit
        test_files = zeroinit.patch(dfs, files, os.path.join(root, "build", "vhdl-zeroinit"))
        if not analyse_project(ghdl, test_files, shared):
            print("GHDL cannot analyse the project")
            return 1
        for name in names:
            ent = BLOCKS[name].get("entity", name)
            result = run_block(ent, BLOCKS[name], port_info(entities[ent]), ghdl, shared, root, libs[ent], generic_defaults(entities[ent], BLOCKS[name].get('generics')), port_type_texts(entities[ent]))
            print("%s: %s" % (name, result))
            if not result.startswith("OK"):
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
