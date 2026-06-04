#!/usr/bin/env python3
"""
mql5_check.py - lightweight static sanity checker for the StellarEA MQL5 source.

This is NOT a compiler. It catches a few classes of mistakes that otherwise
only surface at F7-compile time in MetaEditor:

  1. Preset/input consistency - every key in a .set file must be a real input
     of the EA, and every input should have a value in each preset.
  2. Bracket balance - {}, (), [] balanced across the file.
  3. Unknown function calls - any called identifier that is neither defined in
     the file nor in a curated MQL5 built-in allowlist is flagged for review
     (this catches typos in API names).

Exit code is non-zero if any hard error (1 or 2, or an unknown call) is found.
"""
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EA   = os.path.join(HERE, "..", "StellarEA.mq5")
SETS = [
    os.path.join(HERE, "..", "presets", "StellarEA_EURUSD_M15.set"),
    os.path.join(HERE, "..", "presets", "StellarEA_XAUUSD_M15.set"),
]

# MQL5 built-ins / language keywords this source legitimately uses.
BUILTINS = {
    # language / control
    "if", "for", "while", "switch", "return", "sizeof", "case", "default",
    # output
    "Print", "PrintFormat", "Comment",
    # strings
    "StringLen", "StringSplit", "StringTrimLeft", "StringTrimRight",
    "StringToTime", "StringFormat", "IntegerToString", "DoubleToString",
    "EnumToString",
    # arrays
    "ArrayResize", "ArraySize", "ArrayInitialize",
    # math
    "MathFloor", "NormalizeDouble",
    # time
    "TimeCurrent", "TimeToStruct",
    # series / rates
    "iTime", "iClose", "iLow", "iHigh", "iOpen",
    # indicators
    "iMA", "iADX", "iRSI", "iBands", "iATR", "CopyBuffer", "IndicatorRelease",
    # symbol / account
    "SymbolInfoDouble", "SymbolInfoInteger", "SymbolInfoString",
    "AccountInfoDouble", "AccountInfoString",
    # positions
    "PositionsTotal", "PositionGetTicket", "PositionGetString",
    "PositionGetInteger", "PositionGetDouble",
    # history / deals
    "HistorySelect", "HistoryDealsTotal", "HistoryDealGetTicket",
    "HistoryDealGetString", "HistoryDealGetInteger", "HistoryDealGetDouble",
    # calendar
    "CalendarValueHistory", "CalendarEventById",
    # files
    "FileOpen", "FileWrite", "FileClose", "GetLastError",
    # errors
}


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_comments_strings(src):
    """Remove // and /* */ comments and string/char literals so token scans
    don't trip over them. Replaces strings with empty quotes."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"//[^\n]*", " ", src)
    src = re.sub(r'"(\\.|[^"\\])*"', '""', src)
    src = re.sub(r"'(\\.|[^'\\])*'", "''", src)
    return src


def check_brackets(src):
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set("([{")
    stack = []
    line = 1
    errors = []
    for ch in src:
        if ch == "\n":
            line += 1
        elif ch in opens:
            stack.append((ch, line))
        elif ch in pairs:
            if not stack or stack[-1][0] != pairs[ch]:
                errors.append(f"  unbalanced '{ch}' at line {line}")
            else:
                stack.pop()
    for ch, ln in stack:
        errors.append(f"  unclosed '{ch}' opened at line {ln}")
    return errors


def extract_inputs(src):
    # input <type> Name = ...;   (type may include enum/ENUM_*/long/double/etc.)
    return re.findall(r"\binput\s+[\w:<>]+\s+(\w+)\s*=", src)


def extract_func_defs(code):
    """Definitions: <rettype> Name(params) { -- the brace may sit on the next
    line and the parameter list may span multiple lines."""
    defs = set()
    pat = re.compile(
        r"(?ms)^[ \t]*[A-Za-z_][\w:<>]*[ \t]+([A-Za-z_]\w*)[ \t]*\([^;{}]*\)[ \t\r\n]*\{"
    )
    for m in pat.finditer(code):
        defs.add(m.group(1))
    # event handlers
    for h in ("OnInit", "OnDeinit", "OnTick"):
        if re.search(rf"\b{h}\b\s*\(", code):
            defs.add(h)
    return defs


def extract_calls(code):
    calls = set()
    for m in re.finditer(r"(?<![\.\w>])([A-Za-z_]\w*)\s*\(", code):
        calls.add(m.group(1))
    return calls


def main():
    ea_raw = read(EA)
    code = strip_comments_strings(ea_raw)

    inputs = set(extract_inputs(ea_raw))
    print(f"[info] EA inputs found: {len(inputs)}")

    hard = 0
    soft = 0

    # 1. brackets
    berr = check_brackets(code)
    if berr:
        hard += len(berr)
        print("[FAIL] bracket balance:")
        print("\n".join(berr))
    else:
        print("[ok]   brackets balanced")

    # 2. preset consistency
    for sp in SETS:
        name = os.path.basename(sp)
        keys = []
        for ln in read(sp).splitlines():
            ln = ln.strip()
            if not ln or ln.startswith(";"):
                continue
            m = re.match(r"([A-Za-z_]\w*)\s*=", ln)
            if m:
                keys.append(m.group(1))
        keyset = set(keys)
        unknown = sorted(keyset - inputs)
        missing = sorted(inputs - keyset)
        dups = sorted({k for k in keys if keys.count(k) > 1})
        if unknown:
            hard += len(unknown)
            print(f"[FAIL] {name}: keys not matching any EA input: {unknown}")
        if dups:
            hard += len(dups)
            print(f"[FAIL] {name}: duplicate keys: {dups}")
        if missing:
            soft += len(missing)
            print(f"[warn] {name}: inputs without a preset value: {missing}")
        if not unknown and not missing and not dups:
            print(f"[ok]   {name}: all {len(keyset)} keys map 1:1 to EA inputs")

    # 3. unknown function calls
    defs = extract_func_defs(code)
    calls = extract_calls(code)
    known = defs | BUILTINS | inputs
    unknown_calls = sorted(c for c in calls if c not in known)
    if unknown_calls:
        hard += len(unknown_calls)
        print(f"[FAIL] calls to unknown functions (typo or missing builtin in allowlist): {unknown_calls}")
    else:
        print(f"[ok]   all {len(calls)} call targets are defined or known builtins")

    print(f"\nSummary: {hard} hard issue(s), {soft} warning(s).")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
