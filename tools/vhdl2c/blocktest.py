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
    "acia_63f50": dict(clocks=["e", "sysclk"], resets={"rst_n": 0}, warm=3, cycles=4000, change=0.15),
    "wdg_63f46": dict(clocks=["e", "sysclk"], resets={"rst_n": 0}, warm=3, cycles=3000, change=0.2),
}


def port_info(entity):
    from vtypes import type_of
    ports = []
    p = nodes.Get_Port_Chain(entity)
    while p:
        ct = type_of(nodes.Get_Type(p))
        ports.append((frontend.ident(p), ct, nodes.Get_Mode(p)))
        p = nodes.Get_Chain(p)
    return ports


def is_in(mode):
    return mode == nodes.Iir_Mode.In_Mode if hasattr(nodes.Iir_Mode, "In_Mode") else mode == 1


def vhdl_bench(name, ports, cfg, lib="work"):
    ins = [(n, ct) for n, ct, m in ports if m == nodes.Iir_Mode.In_Mode]
    outs = [(n, ct) for n, ct, m in ports if (n, ct) not in ins]
    clocks = [c.lower() for c in cfg["clocks"]]
    data_in = [(n, ct) for n, ct in ins if n.lower() not in clocks]

    def decl(n, ct):
        if ct.kind == "bit":
            return "std_logic"
        return "std_logic_vector(%d downto 0)" % (ct.width - 1)

    o = []
    o.append("library ieee;\nuse ieee.std_logic_1164.all;\nuse std.textio.all;\n")
    if lib != "work":
        o.append("library %s;\n" % lib)
    o.append("entity tb is\nend entity tb;\n")
    o.append("architecture sim of tb is")
    for n, ct in ins:
        o.append("    signal %s : %s := %s;" % (n, decl(n, ct), "'0'" if ct.kind == "bit" else "(others => '0')"))
    for n, ct in outs:
        o.append("    signal %s : %s;" % (n, decl(n, ct)))
    o.append("begin")
    o.append("    DUT : entity %s.%s port map (%s);" % (lib, name, ", ".join("%s => %s" % (n, n) for n, ct, m in ports)))
    o.append("    process")
    o.append('        file stim : text open read_mode is "stim.txt";')
    o.append('        file result : text open write_mode is "ghdl.out";')
    o.append("        variable l : line;")
    for n, ct in data_in:
        o.append("        variable v_%s : %s;" % (n, decl(n, ct)))
    o.append("        procedure dump is")
    o.append("            variable o : line;")
    o.append("        begin")
    for n, ct in outs:
        o.append("            write(o, to_string(to_x01(%s)) & \" \");" % n)
    o.append("            writeline(result, o);")
    o.append("        end procedure;")
    o.append("    begin")
    o.append("        wait for 1 ns;")
    o.append("        while not endfile(stim) loop")
    o.append("            readline(stim, l);")
    for n, ct in data_in:
        o.append("            read(l, v_%s);" % n)
    for n, ct in data_in:
        o.append("            %s <= v_%s;" % (n, n))
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


def c_bench(name, ports, cfg):
    ins = [(n, ct) for n, ct, m in ports if m == nodes.Iir_Mode.In_Mode]
    outs = [(n, ct) for n, ct in [(n, ct) for n, ct, m in ports] if (n, ct) not in ins]
    clocks = [c.lower() for c in cfg["clocks"]]
    data_in = [(n, ct) for n, ct in ins if n.lower() not in clocks]
    o = []
    o.append('#include <stdio.h>\n#include <string.h>\n\n#include "%s.h"\n' % name)
    o.append("static uint64_t bits(const char *s, size_t w)\n{\n    uint64_t v = 0;\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        v = (v << 1) | (s[i] == '1' || s[i] == 'H');\n    }\n    return v;\n}\n")
    o.append("static void put(const vs_sig *s, size_t w)\n{\n    size_t i;\n")
    o.append("    for (i = 0; i < w; i++)\n    {\n        putchar(((s->cur >> (w - 1 - i)) & 1) ? '1' : '0');\n    }\n    putchar(' ');\n}\n")
    o.append("int main(int argc, char **argv)\n{")
    o.append("    vs_kernel k;\n    %s dut;\n    char line[4096];\n    FILE *f, *trace = NULL;\n    long phase = 0;\n" % name)
    for n, ct, m in ports:
        o.append("    vs_sig p_%s;" % n)
    o.append("")
    o.append("    if (argc < 2 || (f = fopen(argv[1], \"r\")) == NULL)\n    {\n        return 2;\n    }")
    o.append("    if (argc > 2)\n    {\n        trace = fopen(argv[2], \"w\");\n    }")
    o.append("    vs_kernel_init(&k);")
    for n, ct, m in ports:
        o.append("    vs_register_signal(&k, &p_%s, 0);" % n)
    for n, ct, m in ports:
        o.append('    vs_name(&k, &p_%s, NULL, "%s", %d);' % (n, n, ct.width))
    o.append('    %s_create(&k, &dut, "dut", %s);' % (name, ", ".join("&p_%s" % n for n, ct, m in ports)))
    o.append("    vs_settle(&k);")
    o.append("    while (fgets(line, sizeof(line), f) != NULL)\n    {\n        char *tok;")
    first = True
    for n, ct in data_in:
        o.append("        tok = %s;" % ("strtok(line, \" \\n\")" if first else "strtok(NULL, \" \\n\")"))
        o.append("        vs_drive(&p_%s, bits(tok, %d));" % (n, ct.width))
        first = False
    for phase in (0, 1):
        for c in clocks:
            o.append("        vs_drive(&p_%s, %d);" % (c, phase))
        o.append("        vs_settle(&k);")
        for n, ct in outs:
            o.append("        put(&p_%s, %d);" % (n, ct.width))
        o.append("        putchar('\\n');")
        o.append("        if (trace != NULL)\n        {\n            vs_dump(&k, trace, phase);\n        }\n        phase++;")
    o.append("    }\n    if (trace != NULL)\n    {\n        fclose(trace);\n    }\n    fclose(f);\n    vs_kernel_free(&k);\n    return 0;\n}")
    return "\n".join(o) + "\n"


def stimulus(ports, cfg, seed):
    rnd = random.Random(seed)
    clocks = [c.lower() for c in cfg["clocks"]]
    ins = [(n, ct) for n, ct, m in ports if (m == nodes.Iir_Mode.In_Mode) and n.lower() not in clocks]
    cur = {n: rnd.getrandbits(ct.width) for n, ct in ins}
    resets = {k.lower(): v for k, v in cfg["resets"].items()}
    lines = []
    reset_left = 3
    for _ in range(cfg["cycles"]):
        if reset_left == 0 and rnd.random() < 0.01:
            reset_left = rnd.randint(1, 3)
        for n, ct in ins:
            if n.lower() in resets:
                continue
            if rnd.random() < cfg["change"]:
                cur[n] = rnd.getrandbits(ct.width)
        row = []
        for n, ct in ins:
            if n.lower() in resets:
                active = resets[n.lower()]
                v = active if reset_left else 1 - active
            else:
                v = cur[n]
            row.append(format(v, "0%db" % ct.width))
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


def trace_diff(ghdl, shared, work, tb, wd, pp, skip):
    """Reruns both sides with every named signal traced, and reports the first diverging signals."""
    import vcdcmp
    vcd = os.path.join(work, "dump.vcd")
    if not run([ghdl, "--elab-run"] + STD + [wd, pp, tb, "--vcd=" + vcd], work, quiet=True):
        return "   (no trace : GHDL failed)"
    run(["./tb_c", "stim.txt", "c.trace"], work, quiet=True)
    r = vcdcmp.compare(vcd, os.path.join(work, "c.trace"), skip_phases=skip)
    if r is None:
        return None
    phase, diffs = r
    out = ["   first internal difference at phase %d (cycle %d, clocks %s) :" % (phase, phase // 2, "low" if phase % 2 == 0 else "high")]
    out += ["      %-40s ghdl=%s c=%s" % d for d in diffs]
    return "\n".join(out)


def run_block(name, cfg, ports, ghdl, shared, root, lib="work"):
    with tempfile.TemporaryDirectory() as work:
        open(os.path.join(work, "tb.c"), "w").write(c_bench(name, ports, cfg))
        open(os.path.join(work, "stim.txt"), "w").write(stimulus(ports, cfg, 7))
        tb = "tb_" + name
        vhd = os.path.join(shared, tb + ".vhd")
        open(vhd, "w").write(vhdl_bench(name, ports, cfg, lib).replace("entity tb ", "entity %s " % tb).replace("entity tb is", "entity %s is" % tb)
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
            os.makedirs(keep, exist_ok=True)
            open(os.path.join(keep, name + ".c.out"), "w").write(out)
            for f in ("ghdl.out", "stim.txt", "tb.c"):
                shutil.copy(os.path.join(work, f), os.path.join(keep, name + "." + f))
        skip = 2 * cfg["warm"]
        a = [x.strip() for x in open(os.path.join(work, "ghdl.out")).read().split("\n")][skip:]
        b = [x.strip() for x in out.split("\n")][skip:]
        def same(x, y):
            """Equal, except that a bit that GHDL reports as 'X' (a 'U' signal, never assigned) matches anything."""
            return len(x) == len(y) and all(p == q or p == "X" for p, q in zip(x, y))

        if len(a) == len(b) and all(same(x, y) for x, y in zip(a, b)):
            internal = trace_diff(ghdl, shared, work, tb, wd, pp, skip) if cfg.get("trace", True) else None
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
            result = run_block(name, BLOCKS[name], port_info(entities[name]), ghdl, shared, root, libs[name])
            print("%s: %s" % (name, result))
            if not result.startswith("OK"):
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
