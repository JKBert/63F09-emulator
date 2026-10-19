"""Compares the signals of a GHDL VCD trace with the trace dumped by the C test bench.

The C bench dumps, after each phase, "<phase> <name> <value>" for the named signals that changed
(names are "dut.<signal>" for the signals of the block, "<port>" for the bench's own signals).
The VCD of the VHDL bench has the same names under the scopes tb/dut. A phase p ends at
1 ns + 5 ns * (p + 1) : the state compared is the one just before that instant.
"""

import re
import sys

FS_PER_NS = 1000000


def parse_vcd(path):
    """Returns {name: [(time_fs, bitstring)]} for the variables of the file ; names are
    lower case, scopes joined by '.', without the top scope."""
    names = {}          # id -> [name...]
    widths = {}
    scope = []
    series = {}
    time = 0
    in_defs = True
    with open(path) as f:
        for line in f:
            line = line.strip()
            if in_defs:
                if line.startswith("$scope"):
                    scope.append(line.split()[2].lower())
                elif line.startswith("$upscope"):
                    scope.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    width, ident, nm = int(parts[2]), parts[3], parts[4].lower()
                    full = ".".join(scope[1:] + [nm])
                    names.setdefault(ident, []).append(full)
                    widths[full] = width
                    series.setdefault(full, [])
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue
            if not line or line.startswith("$"):
                continue
            if line[0] == "#":
                time = int(line[1:])
                continue
            if line[0] in "bB":
                val, ident = line[1:].split()
            elif line[0] in "rR":
                continue
            else:
                val, ident = line[0], line[1:]
            for full in names.get(ident, []):
                w = widths[full]
                bits = val.lower().rjust(w, val[0].lower() if val[0] in "xuzwl-" else "0")[-w:] if w > 1 else val.lower()
                series[full].append((time, bits))
    return series, widths


def parse_c_trace(path):
    changes = {}
    last_phase = -1
    with open(path) as f:
        for line in f:
            p, name, val = line.split()
            changes.setdefault(int(p), []).append((name.lower(), int(val)))
            last_phase = max(last_phase, int(p))
    return changes, last_phase


def compare(vcd_path, c_path, widths_c=None, skip_phases=0, limit=40):
    """Returns (phase, [(name, ghdl, c)]) of the first phase where a common signal differs, or None."""
    series, widths = parse_vcd(vcd_path)
    changes, last = parse_c_trace(c_path)
    cstate = {}
    idx = {name: 0 for name in series}
    vstate = {}
    for p in range(last + 1):
        for name, val in changes.get(p, []):
            cstate[name] = val
        t_end = (1 + 5 * (p + 1)) * FS_PER_NS
        for name, ser in series.items():
            i = idx[name]
            while i < len(ser) and ser[i][0] < t_end:
                vstate[name] = ser[i][1]
                i += 1
            idx[name] = i
        if p < skip_phases:
            continue
        diffs = []
        for name, cval in cstate.items():
            if name not in vstate:
                continue
            bits = vstate[name]
            if re.search("[xuzwl-]", bits):
                continue
            w = widths[name]
            vval = int(bits, 2)
            mask = (1 << w) - 1
            if (cval & mask) != vval:
                diffs.append((name, bits, format(cval & mask, "0%db" % w)))
        if diffs:
            return p, sorted(diffs)[:limit]
    return None


if __name__ == "__main__":
    r = compare(sys.argv[1], sys.argv[2])
    print("identical" if r is None else r)
