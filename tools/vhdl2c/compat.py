"""Rewrites of the VHDL sources for the constructs that Vivado accepts and GHDL does not.

The sources are never modified : a patched copy is written to the build directory and analysed
instead. Every rewrite keeps the meaning of the construct :

  conditional port actuals    "FORMAL => A when C else B" is not VHDL-2008 (Vivado accepts it). It is an
                              expression used as an actual, that is an implicit signal assigned by the
                              expression : the rewrite makes that signal explicit in a block around the
                              instance (so it also works inside a generate, whose parameters it may use).

  non-static sensitivity      "process(X(dynamic_index)(i), ...)" : the sensitivity set holds the longest static
                              prefix of the name, here X. The rewrite lists that prefix.

  translate_off zones         "-- synthesis translate_off" ... "-- synthesis translate_on" : simulation-only code
                              (checkers with `wait` statements, which GHDL cannot canonicalise). Not hardware, so
                              dropped ; the line numbers of the rest of the file are kept.
"""

import os
import re

_INSTANCE = re.compile(
    r"(?P<label>\w+)\s*:\s*(?P<comp>(?:entity\s+)?[\w.]+)\s*"
    r"(?P<gen>generic\s+map\s*\(.*?\)\s*)?"
    r"port\s+map\s*\((?P<ports>.*?)\)\s*;",
    re.S | re.I,
)
_COND_ASSOC = re.compile(
    r"^\s*(?P<formal>\w+(?:\([^)]*\))?)\s*=>\s*(?P<a>.+?)\s+when\s+(?P<cond>.+?)\s+else\s+(?P<b>.+?)\s*$",
    re.S | re.I,
)
_COUNTER = [0]


def _split_top_level(text):
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def fix_conditional_actuals(text):
    def repl(m):
        ports = re.sub(r"--[^\n]*", "", m.group("ports"))
        if not re.search(r"\bwhen\b", ports, re.I):
            return m.group(0)
        decls, assigns, assocs = [], [], []
        for assoc in _split_top_level(ports):
            c = _COND_ASSOC.match(assoc)
            if c is None:
                assocs.append(assoc.strip())
                continue
            # The actuals of this design are std_logic ; the analysis fails if one is not.
            _COUNTER[0] += 1
            sig = "COND_ACTUAL_%d" % _COUNTER[0]
            decls.append("signal %s : std_logic;" % sig)
            assigns.append("%s <= %s when %s else %s;" % (sig, c.group("a").strip(), c.group("cond").strip(), c.group("b").strip()))
            assocs.append("%s => %s" % (c.group("formal"), sig))
        label = m.group("label")
        inst = "%s : %s %sport map (%s);" % (label, m.group("comp"), m.group("gen") or "", ", ".join(assocs))
        return "%s_COND : block\n%s\nbegin\n%s\n%s\nend block %s_COND;" % (
            label, "\n".join(decls), "\n".join(assigns), inst, label)

    return _INSTANCE.sub(repl, text)


def _static_prefix_sensitivity(names):
    """Rewrites, in the sensitivity lists of the processes of one file, the given names by their
    longest static prefix."""
    def fix(text):
        for full, prefix in names:
            # only inside a process sensitivity list : the name must be followed by ',' or ')' there
            text = re.sub(r"(process\s*\([^;]*?)" + re.escape(full), lambda m: m.group(1) + prefix, text, flags=re.I | re.S)
        return text
    return fix


def fix_incv(text):
    """Opt-in (VHDL2C_FIX_INCV=1), for checking a correction without touching the sources : the decoder of 107C INCV
    takes Q as its operand where DECV (107A) takes V."""
    return re.sub(r"(-- 107C : INCV immediate\s+LEFT_CTRL <= )REG_Q_LEFT", r"\1REG_V_LEFT", text)


def fix_spi_decode(text):
    """Opt-in (VHDL2C_FIX_SPI_DECODE=1) : the 63F52 has four registers (ADDR is 2 bits wide, the chip-select register is
    at +2 and +3) but SoC.vhd selects it for x"000" and x"001" only."""
    return re.sub(r'when x"000" \| x"001"(?: \| x"010" \| x"011")? => CS\(MUX_SPI0\) <= \'1\';',
                  'when x"000" | x"001" | x"002" | x"003" => CS(MUX_SPI0) <= \'1\';', text)


def fix_pia_read(text):
    """Opt-in (VHDL2C_FIX_PIA_READ=1) : PIA_READ returns the output register for an input bit (DDR = 0) and the pad for
    an output bit ; a 6821 does the opposite."""
    return text.replace("if PORT_DDR(i) = '0' then\n                        -- Input : read only data in PORT register",
                        "if PORT_DDR(i) = '1' then\n                        -- Input : read only data in PORT register", 1)


def drop_translate_off(text):
    """Removes the translate_off zones (simulation-only checkers) and keeps the number of lines."""
    return re.sub(r"--\s*synthesis\s+translate_off.*?--\s*synthesis\s+translate_on",
                  lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S | re.I)


def fix_empty_statement(text):
    """`end if;;` : GHDL rejects the empty statement (error "extra ';' ignored"), other tools accept it."""
    return re.sub(r";;", ";", text)


def fix_bac_eirq(text):
    """Opt-in (VHDL2C_FIX_BAC_EIRQ=1) : the 63F81 forwards EIRQ_n to a core on falling_edge(E), and E stops when the cores
    run from their caches : an interrupt is never delivered. Combinational routing instead."""
    old_head = "process(RESET_n, E) is\n        begin\n            if RESET_n = '0' then\n                for i in 0 to 23 loop"
    i = text.find(old_head)
    if i < 0:
        return text
    j = text.index("end process;", i) + len("end process;")
    new = """process(RESET_n, EIRQ_n, SIGNAL_LAST_INTERRUPTED_CPU) is
        begin
            for i in 0 to 23 loop
                for j in 0 to NCPUS - 1 loop
                    CPU_EIRQ_n(j)(i) <= '1';
                end loop;
            end loop;
            if RESET_n /= '0' then
                for i in 0 to 23 loop
                    CPU_EIRQ_n(SIGNAL_LAST_INTERRUPTED_CPU(i + 3))(i) <= EIRQ_n(i);
                end loop;
            end if;
        end process;"""
    return text[:i] + new + text[j:]


def fix_ptm_sysclk(text):
    """Opt-in (VHDL2C_FIX_PTM_SYSCLK=1) : TIMER runs on falling_edge(SYSCLK), where `SYSCLK = '1'` is never true : with
    SYSCLK as the clock source the counter never counts. Every clock of the process is one SYSCLK period."""
    text = text.replace("(SYSCLK /= C_n_OLD) and (SYSCLK = '1')", "true")
    # the STATUS process also has to run without E
    return text.replace("STATUS : process(E, RST_n) is", "STATUS : process(SYSCLK, RST_n) is").replace(
        "            if falling_edge(E) then\n                for i in 1 to 3 loop",
        "            if falling_edge(SYSCLK) then\n                for i in 1 to 3 loop")


PATCHES = {
    "61F64x1": [fix_conditional_actuals],
    "63F52": [fix_conditional_actuals],
    "SoC": [fix_spi_decode] if os.environ.get("VHDL2C_FIX_SPI_DECODE") else [],
    "63F40": [fix_empty_statement] + ([fix_ptm_sysclk] if os.environ.get("VHDL2C_FIX_PTM_SYSCLK") else []),
    "63F81": [fix_bac_eirq] if os.environ.get("VHDL2C_FIX_BAC_EIRQ") else [],
    "63F21": [fix_pia_read] if os.environ.get("VHDL2C_FIX_PIA_READ") else [],
    "63F09": [fix_incv] if os.environ.get("VHDL2C_FIX_INCV") else [],
    "63F29": [drop_translate_off, _static_prefix_sensitivity([
        ("BANK_ARRAY(CURRENT_RING)(i)", "BANK_ARRAY"),
        ("PAYLOAD_ARRAY(CURRENT_RING)(i)", "PAYLOAD_ARRAY"),
    ])],
}


def patched_path(name, path, build_dir):
    """Returns `path`, or the path of a patched copy when `name` needs a rewrite."""
    fixes = PATCHES.get(name)
    if not fixes:
        return path
    text = open(path, encoding="utf-8", errors="replace").read()
    for fix in fixes:
        text = fix(text)
    os.makedirs(build_dir, exist_ok=True)
    dest = os.path.join(build_dir, os.path.basename(path))
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    return dest
