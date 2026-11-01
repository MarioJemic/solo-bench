"""Hard exam: programming families (levels 1–5). The reference solutions (_*_ref) make the unit tests."""
from .gen_util import _fname, _word


def _rpn_ref(tokens, level):
    st = []
    try:
        for t in tokens:
            if t in ("+", "-", "*", "/", "^"):
                b, a = st.pop(), st.pop()
                if t == "/":
                    if b == 0:
                        return None
                    q = abs(a) // abs(b)
                    st.append(q if (a >= 0) == (b >= 0) else -q)
                else:
                    st.append(a + b if t == "+" else a - b if t == "-" else a * b if t == "*" else a ** b)
            elif t == "neg":
                st.append(-st.pop())
            elif t == "dup":
                st.append(st[-1])
            elif t == "swap":
                st[-1], st[-2] = st[-2], st[-1]
            else:
                st.append(int(t))
    except IndexError:
        return None
    return st[-1] if len(st) == 1 else None


def h_code_rpn(rng, level):
    """Evaluate reverse Polish notation; more operators and error cases per level."""
    f = _fname(rng)
    ops = ["+", "-", "*"] + (["/"] if level >= 2 else []) + (["^", "neg"] if level >= 3 else []) \
        + (["dup", "swap"] if level >= 4 else [])
    spec = ["'+', '-', '*' work on the two top numbers (a b op -> a op b)"]
    if level >= 2:
        spec.append("'/' is integer division rounding toward zero; division by zero -> return None")
    if level >= 3:
        spec.append("'^' is power (exponent >= 0) and 'neg' negates the top number")
    if level >= 4:
        spec.append("'dup' duplicates the top number and 'swap' exchanges the two top numbers")
    spec.append("return None if an operation lacks numbers" + (" or more than one number is left at the end"
                                                                  if level >= 2 else ""))

    def expr():
        toks, depth = [str(rng.randint(-9, 20))], 1
        for _ in range(rng.randint(2, 3 + level)):
            op = rng.choice(ops)
            if op in ("neg", "dup"):
                toks.append(op)
                depth += op == "dup"
            elif op == "swap":
                toks += [str(rng.randint(0, 9)), "swap"]
                depth += 1
            else:
                toks += [str(rng.randint(0, 3) if op == "^" else rng.randint(-9, 20)), op]
        return toks
    cases = [expr() for _ in range(6 + level)] + [["3", "+"], ["2", "3"] if level >= 2 else ["1"]]
    tests = [[[c], _rpn_ref(c, level)] for c in cases]
    return {"cat": "code", "type": "code", "expect": {"func": f, "tests": tests},
            "prompt": f"Write a Python function `{f}(tokens)` that evaluates a list of string tokens in reverse Polish "
                      f"notation with integers (e.g. ['2', '3', '+'] -> 5). Rules: " + "; ".join(spec)
                      + ". Return the integer result. Reply with the code only."}


def _wrap_ref(text, width, level):
    def lines_of(par):
        words = []
        for w in par.split():
            while level >= 3 and len(w) > width:
                words.append(w[:width])
                w = w[width:]
            words.append(w)
        out, cur = [], ""
        for w in words:
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= width:
                cur += " " + w
            else:
                out.append(cur)
                cur = w
        return out + ([cur] if cur else [])
    if level < 5:
        return lines_of(text)
    out = []
    for i, par in enumerate(p for p in text.split("\n\n")):
        if i:
            out.append("")
        out += lines_of(par)
    return out


def h_code_wrap(rng, level):
    """Greedy word wrap; long words are split from level 3, paragraphs kept from level 5."""
    f, width = _fname(rng), rng.randint(8, 14)
    spec = ["greedy: put as many words on a line as fit within `width` characters (words separated by one space)",
            "spaces between words in the input may be repeated; the output uses single spaces"]
    if level >= 3:
        spec.append("a word longer than `width` is cut into pieces of exactly `width` characters (the last piece "
                    "may be shorter), each piece treated as a word")
    if level >= 5:
        spec.append("paragraphs are separated by a blank line ('\\n\\n') in the input; between paragraphs the result "
                    "has one empty string ''")
    spec.append("an empty or blank text returns []")

    def text():
        pars = []
        for _ in range(rng.randint(1, 3) if level >= 5 else 1):
            ws = [_word(rng, rng.randint(1, 3 + (level >= 3) * 4)) for _ in range(rng.randint(3, 6 + level))]
            pars.append(rng.choice([" ", "  "]).join(ws))
        return "\n\n".join(pars)
    cases = [text() for _ in range(5)] + [""]
    tests = [[[c, width], _wrap_ref(c, width, level)] for c in cases]
    return {"cat": "code", "type": "code", "expect": {"func": f, "tests": tests},
            "prompt": f"Write a Python function `{f}(text, width)` that wraps the text into lines and returns the list "
                      f"of lines. Rules: " + "; ".join(spec) + ". Reply with the code only."}


def _cover_ref(iv, gap, level):
    iv = sorted(tuple(x) for x in iv if x[1] > x[0])
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged if level >= 5 else sum(b - a for a, b in merged)


def h_code_cover(rng, level):
    """Intervals: total covered length; gaps merge from level 3, negative numbers from 4, the merged list at 5."""
    f = _fname(rng)
    gap = rng.randint(1, 3) if level >= 3 else 0
    lo = -50 if level >= 4 else 0
    spec = ["intervals are [start, end) pairs of integers; ones with end <= start are ignored"]
    if gap:
        spec.append(f"two intervals whose distance is at most {gap} count as one (the gap between them is covered too)")
    want = ("return the merged intervals as a sorted list of [start, end] lists" if level >= 5 else
            "return the total length covered (overlaps counted once)")

    def ivs():
        out = []
        for _ in range(rng.randint(0, 4 + level)):
            a = rng.randint(lo, 60)
            out.append([a, a + rng.randint(-2, 12)])
        return out
    tests = [[[c], _cover_ref(c, gap, level)] for c in [ivs() for _ in range(7)] + [[]]]
    return {"cat": "code", "type": "code", "expect": {"func": f, "tests": tests},
            "prompt": f"Write a Python function `{f}(intervals)`: " + "; ".join(spec) + f"; {want}. Reply with the "
                      f"code only."}
