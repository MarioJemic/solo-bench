"""Graders: deterministic wherever possible. Writing is scored by a blind judge model (it never learns which
model or module version wrote the answer)."""
import ast
import json
import re
import subprocess
import sys
import tempfile

ALLOWED_IMPORTS = {"math", "itertools", "collections", "functools", "re", "string", "heapq", "bisect", "typing"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "getattr", "setattr",
                   "delattr", "vars", "breakpoint", "exit", "quit", "help", "memoryview", "dir", "type", "object"}
HR_WORDS = {"je", "i", "da", "se", "u", "na", "za", "su", "od", "koji", "što", "kao", "ili", "biljke", "rezultat",
            "jednako", "iznosi", "zbroj", "plus", "to", "su", "ovo", "pomoću", "energiju", "svjetlost", "jest"}
EN_WORDS = {"the", "is", "and", "of", "to", "in", "that", "it", "plants", "result", "equals", "sum", "this"}


def final_answer(text):
    m = re.findall(r"ANSWER\s*[:：]\s*\**\s*(.+)", text or "", re.I)
    return (m[-1] if m else (text or "").strip().splitlines()[-1] if (text or "").strip() else "").strip().strip("*`. ")


def _number(s):
    s = s.replace("−", "-").replace(",", "") if re.search(r"\d,\d{3}\b", s) else s.replace("−", "-").replace(",", ".")
    m = re.findall(r"-?\d+(?:\.\d+)?", s)
    return float(m[0]) if m else None


def g_number(t, text):
    v = _number(final_answer(text))
    ok = v is not None and abs(v - t["expect"]["value"]) <= t["expect"]["tol"] + 1e-9
    return (1.0 if ok else 0.0), f"got {v}, expected {t['expect']['value']}"


def g_word(t, text):
    got = final_answer(text).lower()
    exp = t["expect"]["value"].lower()
    return (1.0 if re.search(rf"\b{re.escape(exp)}\b", got) else 0.0), f"got {got[:40]!r}, expected {exp!r}"


def g_exact(t, text):
    got = (text or "").strip().strip("`").strip()
    return (1.0 if got == t["expect"]["value"] else 0.0), f"got {got[:60]!r}"


def g_json(t, text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return 0.0, "no valid JSON object"
    exp = t["expect"]
    right = sum(1 for k, v in exp.items() if str(data.get(k, "")).strip().lower() == str(v).lower())
    extra = set(data) - set(exp)
    score = right / len(exp) - (0.25 if extra else 0)
    return max(0.0, score), f"{right}/{len(exp)} fields right" + (f", extra keys {sorted(extra)}" if extra else "")


def g_rules(t, text):
    e, body = t["expect"], (text or "").strip()
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    fails = []
    if "lines" in e and len(lines) != e["lines"]:
        fails.append(f"{len(lines)} lines instead of {e['lines']}")
    if "start" in e and not all(ln.lower().startswith(e["start"]) for ln in lines):
        fails.append(f"not all lines start with {e['start']!r}")
    if e.get("plain") and any(re.match(r"^([-*•]|\d+[.)])", ln) for ln in lines):
        fails.append("numbering or bullets")
    if "words" in e and len(re.findall(r"[\w'’-]+", body)) != e["words"]:
        fails.append(f"{len(re.findall(r'[\w’-]+', body))} words instead of {e['words']}")
    if e.get("lowercase") and body != body.lower():
        fails.append("uppercase letters")
    if "sentences" in e:
        sents = [x for x in re.split(r"(?<=[.!?])\s+", body) if x.strip()]
        if len(sents) != e["sentences"]:
            fails.append(f"{len(sents)} sentences instead of {e['sentences']}")
        elif e.get("second_has") and e["second_has"].lower() not in sents[1].lower():
            fails.append(f"second sentence lacks {e['second_has']!r}")
    if e.get("acrostic") and "".join(ln[:1].lower() for ln in lines) != e["acrostic"].lower():
        fails.append(f"first letters spell {''.join(ln[:1] for ln in lines)!r}, not {e['acrostic']!r}")
    if e.get("line_words") and any(len(re.findall(r"[\w'’-]+", ln)) != e["line_words"] for ln in lines):
        fails.append(f"not every line has {e['line_words']} words")
    for c in e.get("forbid") or "":                      # one letter, or several (each one is banned)
        if c.lower() in body.lower():
            fails.append(f"contains the letter {c!r}")
    if e.get("last_word"):
        words = re.findall(r"[\w'’-]+", body)
        if not words or words[-1].lower() != e["last_word"]:
            fails.append(f"last word is {words[-1] if words else None!r}, not {e['last_word']!r}")
    return (1.0 if not fails else 0.0), "; ".join(fails) or "all rules kept"


def is_croatian(text):
    words = re.findall(r"[a-zčćđšž]+", (text or "").lower())
    hr, en = sum(w in HR_WORDS for w in words), sum(w in EN_WORDS for w in words)
    return bool(re.search(r"[čćđšž]", text.lower()) or hr > en) and hr >= en


def g_lang(t, text):
    e = t["expect"]
    low = (text or "").lower()
    fails = []
    if e.get("lang") == "hr" and not is_croatian(low):
        fails.append("not in Croatian")
    for c in e.get("contains", []):
        if c.lower() not in low:
            fails.append(f"missing {c!r}")
    for alts in e.get("any", []):
        if not any(a in low for a in alts):
            fails.append(f"missing one of {alts}")
    return max(0.0, 1 - 0.5 * len(fails)), "; ".join(fails) or "ok"


# ---------------------------------------------------------------- code (sandboxed)
def _extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    return max(blocks, key=len) if blocks else (text or "")


def _code_is_safe(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax error: {e.msg}"
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else [(n.module or "").split(".")[0]]
            if any(m not in ALLOWED_IMPORTS for m in mods):
                return f"import not allowed: {mods}"
        if isinstance(n, ast.Name) and n.id in FORBIDDEN_NAMES:
            return f"name not allowed: {n.id}"
        if isinstance(n, ast.Attribute) and n.attr.startswith("__"):
            return f"attribute not allowed: {n.attr}"
    return None


RUNNER = """
import json, sys
ns = {}
exec(compile(sys.stdin.read(), "answer", "exec"), ns)
f = ns[%r]
out = []
for args, want in json.loads(%r):
    try:
        got = f(*args)
        out.append(got == want or (isinstance(got, tuple) and list(got) == want))
    except Exception as e:
        out.append(False)
print(json.dumps(out))
"""


def g_code(t, text, tmp=None):
    code = _extract_code(text)
    bad = _code_is_safe(code)
    if bad:
        return 0.0, bad
    e = t["expect"]
    if not re.search(rf"def\s+{re.escape(e['func'])}\s*\(", code):
        return 0.0, f"function {e['func']} not defined"
    runner = RUNNER % (e["func"], json.dumps(e["tests"]))      # tests travel as JSON text: None, True stay valid
    try:
        r = subprocess.run([sys.executable, "-I", "-S", "-c", runner], input=code, capture_output=True, text=True,
                           timeout=8, cwd=tmp or tempfile.gettempdir())
        res = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
    except subprocess.TimeoutExpired:
        return 0.0, "timed out"
    except (ValueError, IndexError):
        res = None
    if not isinstance(res, list):
        return 0.0, "crashed: " + (r.stderr.strip().splitlines() or ["?"])[-1][:120]
    return sum(res) / len(res), f"{sum(res)}/{len(res)} tests passed"


# ---------------------------------------------------------------- judge
JUDGE_SYSTEM = ("You are a strict, fair examiner. You grade one answer against the task and the rubric. "
                "You do not know who wrote it. Reply with a one-sentence reason and then a last line "
                "'SCORE: n' with n an integer from 0 to 10.")


def judge_prompt(t, text):
    return (f"TASK:\n{t['prompt']}\n\nRUBRIC: {t['expect'].get('rubric', 'helpful, correct, clear')}; word limit "
            f"{t['expect'].get('max_words', 'none')}.\n\nANSWER TO GRADE:\n<<<\n{(text or '')[:4000]}\n>>>")


def parse_judge(reply):
    m = re.findall(r"SCORE\s*[:：]\s*(\d+(?:\.\d+)?)", reply or "", re.I)
    if not m:
        return None
    return max(0.0, min(10.0, float(m[-1]))) / 10


def g_judge_local(t, text):
    """Part of the writing score that needs no judge: the word limit and a non-empty answer."""
    words = len(re.findall(r"[\w'’-]+", text or ""))
    limit = t["expect"].get("max_words")
    if not words:
        return 0.0, "empty"
    if limit and words > limit * 1.1:
        return 0.3, f"{words} words, limit {limit}"
    return 1.0, f"{words} words"


def g_list(t, text):
    """Names in a given order (comma separated): all right = 1, otherwise the share in the right place."""
    got = [x.strip().strip("*`'\".").lower() for x in final_answer(text).split(",") if x.strip()]
    exp = [x.lower() for x in t["expect"]["value"]]
    if got == exp:
        return 1.0, "all in order"
    right = sum(1 for a, b in zip(got, exp) if a == b)
    return round(0.5 * right / len(exp), 3), f"{right}/{len(exp)} in the right place: {', '.join(got)[:80]}"


GRADERS = {"number": g_number, "word": g_word, "exact": g_exact, "json": g_json, "rules": g_rules, "lang": g_lang,
           "list": g_list}
