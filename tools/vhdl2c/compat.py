"""Rewrites of the VHDL sources for the constructs that Vivado accepts and GHDL does not.

The sources are never modified : a patched copy is written to the build directory and analysed
instead. Every rewrite keeps the meaning of the construct :

  conditional port actuals    "FORMAL => A when C else B" is not VHDL-2008 (Vivado accepts it). It is an
                              expression used as an actual, that is an implicit signal assigned by the
                              expression : the rewrite makes that signal explicit in a block around the
                              instance (so it also works inside a generate, whose parameters it may use).

  non-static sensitivity      "process(X(dynamic_index)(i), ...)" : the sensitivity set holds the longest static
                              prefix of the name, here X. The rewrite lists that prefix.
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


PATCHES = {
    "61F64x1": [fix_conditional_actuals],
    "63F52": [fix_conditional_actuals],
    "63F29": [_static_prefix_sensitivity([
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
