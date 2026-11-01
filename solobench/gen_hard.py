"""The hard exam: task families with difficulty levels 1–5, so even the strongest models stay below 100 %.

Each family is a generator g(rng, level) -> task. Every level is the same kind of work, only bigger or with more
traps (more steps, longer texts, more people, more rules), so a family's levels form one scale. Graders are all
deterministic. The level of each family adapts (hard.py): the best model should get about 75 %.
"""
import itertools
from datetime import date, timedelta

from .gen_hard_code import h_code_cover, h_code_rpn, h_code_wrap
from .gen_util import _word

ANSWER = "\nEnd with a last line in the form: ANSWER: <answer>"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FIRST = ["Ana", "Marko", "Ivana", "Luka", "Petra", "Josip", "Maja", "Tomislav", "Ema", "Filip", "Lucija", "Karlo",
         "Nika", "Ivan", "Sara", "Mateo", "Lea", "David", "Iva", "Dino"]
LAST = ["Horvat", "Kovač", "Babić", "Marić", "Jurić", "Novak", "Knežević", "Vuković", "Perić", "Tomić", "Pavlović",
        "Božić", "Blažević", "Grgić", "Šarić"]
CITIES = ["Zagreb", "Split", "Rijeka", "Osijek", "Zadar", "Pula", "Dubrovnik", "Varaždin", "Šibenik", "Karlovac"]


# ------------------------------------------------------------------ math
def h_chain(rng, level):
    """A long integer expression with brackets: more operations and bigger numbers per level."""
    n_ops, digits = 2 + 2 * level, min(1 + level, 4)

    def num():
        return rng.randint(10 ** (digits - 1), 10 ** digits - 1)
    expr = str(num())
    for _ in range(n_ops):
        op = rng.choice(["+", "-", "*"] if level > 1 else ["+", "-"])
        part = str(num())
        if rng.random() < 0.3:
            part = f"({part} {rng.choice('+-')} {num()})"
        expr = f"({expr} {op} {part})" if rng.random() < 0.4 else f"{expr} {op} {part}"
    value = eval(expr, {"__builtins__": {}})          # noqa: S307 - our own digits and operators only
    shown = expr.replace("*", "×").replace("-", "−")
    return {"cat": "math", "type": "number", "expect": {"value": value, "tol": 0},
            "prompt": f"Compute exactly: {shown}" + ANSWER}


def h_money(rng, level):
    """A price through several changes (percentages, fees, splitting); rounding only at the very end."""
    price = round(rng.uniform(40, 900), 2)
    steps, text = [], [f"An item costs {price} EUR."]
    vat = False
    for _ in range(1 + 2 * level):
        kind = rng.choice(["pct+", "pct-", "fee", "pct+", "pct-"] + (["vat"] if level >= 3 and not vat else []))
        vat = vat or kind == "vat"
        if kind == "pct+":
            p = rng.choice([3, 4.5, 7, 12, 15, 20])
            steps.append(lambda x, p=p: x * (1 + p / 100))
            text.append(f"The price rises by {p}%.")
        elif kind == "pct-":
            p = rng.choice([5, 8, 10, 12.5, 25, 30])
            steps.append(lambda x, p=p: x * (1 - p / 100))
            text.append(f"Then it is discounted by {p}%.")
        elif kind == "fee":
            f = rng.choice([2.5, 4, 9.99, 15])
            steps.append(lambda x, f=f: x + f)
            text.append(f"A fixed fee of {f} EUR is added.")
        else:
            steps.append(lambda x: x / 1.25)
            text.append("The price shown included 25% VAT; from now on work with the price without VAT.")
    x = price
    for s in steps:
        x = s(x)
    people = rng.randint(2, 6) if level >= 2 else 1
    if people > 1:
        text.append(f"The final amount is split equally among {people} people.")
        x /= people
    ask = "How much does each person pay" if people > 1 else "What is the final price"
    return {"cat": "math", "type": "number", "expect": {"value": round(x, 2), "tol": 0.011},
            "prompt": " ".join(text) + f" {ask}, in EUR rounded to cents? Do not round in between." + ANSWER}


DIGITS36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _to_base(n, b):
    out = ""
    while n:
        n, r = divmod(n, b)
        out = DIGITS36[r] + out
    return out or "0"


def h_base(rng, level):
    """Number base conversion; bigger numbers and stranger bases per level."""
    bases = [2, 8, 16] if level <= 2 else [2, 3, 5, 7, 8, 12, 16, 36]
    a, b = rng.sample(bases, 2)
    n = rng.randint(10 ** (1 + level), 10 ** (2 + level))
    return {"cat": "math", "type": "word", "expect": {"value": _to_base(n, b)},
            "prompt": f"Convert the base-{a} number {_to_base(n, a)} to base {b} (digits 0-9 then a-z, lowercase)."
                      + ANSWER}


# ------------------------------------------------------------------ reasoning
def h_order(rng, level):
    """Who is k-th tallest, from shuffled comparisons in mixed wording with redundant facts."""
    n = 4 + level
    people = rng.sample(FIRST, n)                       # tallest -> shortest
    facts = []
    for i in range(n - 1):
        a, b = people[i], people[i + 1]
        facts.append(rng.choice([f"{a} is taller than {b}.", f"{b} is shorter than {a}."]))
    for _ in range(level):                              # true but redundant facts
        i, j = sorted(rng.sample(range(n), 2))
        facts.append(rng.choice([f"{people[i]} is taller than {people[j]}.", f"{people[j]} is not taller than {people[i]}."]))
    rng.shuffle(facts)
    k = 1 if level == 1 else rng.randint(2, n - 1)
    nth = {1: "tallest", 2: "second tallest", 3: "third tallest", 4: "fourth tallest", 5: "fifth tallest",
           6: "sixth tallest", 7: "seventh tallest", 8: "eighth tallest"}[k]
    return {"cat": "reason", "type": "word", "expect": {"value": people[k - 1]},
            "prompt": " ".join(facts) + f" Everyone has a different height. Who is the {nth}?" + ANSWER}


def _clue_ok(clue, pos):
    kind, a, b = clue
    if kind == "at":
        return pos[a] == b
    if kind == "not_at":
        return pos[a] != b
    if kind == "left":
        return pos[a] < pos[b]
    if kind == "right_next":
        return pos[a] == pos[b] + 1
    if kind == "next":
        return abs(pos[a] - pos[b]) == 1
    return abs(pos[a] - pos[b]) > 1                     # "apart": not neighbours


def _clue_text(clue):
    kind, a, b = clue
    return {"at": f"{a} lives in house {b if isinstance(b, str) else b + 1}.",
            "not_at": f"{a} does not live in house {b if isinstance(b, str) else b + 1}.",
            "left": f"{a} lives somewhere to the left of {b}.",
            "right_next": f"{a} lives directly to the right of {b}.",
            "next": f"{a} and {b} are neighbours.",
            "apart": f"{a} and {b} are not neighbours."}[kind]


def h_houses(rng, level):
    """A logic puzzle: n people in n houses in a row; clues are added until exactly one arrangement fits."""
    n = 3 + min(level, 4)
    people = rng.sample(FIRST, n)
    truth = people[:]
    rng.shuffle(truth)
    pos = {p: i for i, p in enumerate(truth)}
    kinds = ["left", "right_next", "next", "apart", "not_at"] + (["at"] if level <= 2 else [])
    perms = [dict(zip(p, range(n))) for p in itertools.permutations(people)]
    clues = []
    while len(perms) > 1:
        kind = rng.choice(kinds)
        a, b = rng.sample(people, 2)
        clue = (kind, a, rng.randrange(n) if kind in ("at", "not_at") else b)
        if not _clue_ok(clue, pos):
            continue
        left = [p for p in perms if _clue_ok(clue, p)]
        if len(left) < len(perms):
            perms, clues = left, clues + [clue]
    rng.shuffle(clues)
    return {"cat": "reason", "type": "list", "expect": {"value": truth},
            "prompt": f"{n} people ({', '.join(sorted(people))}) live in {n} houses in a row, numbered 1 to {n} from "
                      f"left to right, one person per house.\n" + "\n".join(_clue_text(c) for c in clues)
                      + f"\nWho lives in each house? Give the names from house 1 to house {n}, separated by commas."
                      + ANSWER}


def h_count(rng, level):
    """Counting a letter in a longer and longer text (models read tokens, not letters)."""
    words = [_word(rng, rng.randint(1, 4)) for _ in range(12 * level)]
    text = " ".join(words)
    letter = rng.choice("aeiolmnrst")
    if level >= 4:
        n = sum(1 for w in words if letter in w)
        return {"cat": "reason", "type": "number", "expect": {"value": n, "tol": 0},
                "prompt": f"How many WORDS in this text contain the letter '{letter}' at least once?\n{text}" + ANSWER}
    return {"cat": "reason", "type": "number", "expect": {"value": text.count(letter), "tol": 0},
            "prompt": f"How many times does the letter '{letter}' occur in this text?\n{text}" + ANSWER}


def h_workdays(rng, level):
    """The N-th working day after a date, skipping weekends (and listed holidays from level 3)."""
    start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 900))
    n = rng.randint(5, 12) * level
    holidays = set()
    if level >= 3:
        while len(holidays) < level:
            d = start + timedelta(days=rng.randint(1, n + n // 2))
            if d.weekday() < 5:
                holidays.add(d)
    d, left = start, n
    while left:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            left -= 1
    extra = (" These days are public holidays and are not working days: "
             + ", ".join(h.isoformat() for h in sorted(holidays)) + ".") if holidays else ""
    return {"cat": "reason", "type": "word", "expect": {"value": d.isoformat()},
            "prompt": f"Working days are Monday to Friday.{extra} Which date is the {n}th working day after "
                      f"{start.isoformat()} ({DAYS[start.weekday()]}), not counting that day itself? Give YYYY-MM-DD."
                      + ANSWER}


# ------------------------------------------------------------------ extraction
def h_people(rng, level):
    """Ages of several people from a chatty text with traps (past ages, pets, years) -> JSON {name: age}."""
    n = 1 + level
    names = []
    while len(names) < n:
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if nm.split()[0] not in [x.split()[0] for x in names]:
            names.append(nm)
    ages, parts = {}, []
    for nm in names:
        age = rng.randint(19, 81)
        ages[nm] = age
        first = nm.split()[0]
        style = rng.randrange(4 if level >= 3 else 2)
        if style == 0:
            parts.append(f"{nm} is {age} and lives in {rng.choice(CITIES)}.")
        elif style == 1:
            parts.append(f"Born in {2026 - age}, {nm} celebrated a birthday earlier this year (2026).")
        elif style == 2:
            k = rng.randint(2, 9)
            parts.append(f"{k} years ago {first} ({nm}) was {age - k}.")
        else:
            k = rng.randint(2, 6)
            parts.append(f"In {k} years {nm} will turn {age + k}.")
        if level >= 2 and rng.random() < 0.6:
            parts.append(f"{first}'s dog is {rng.randint(2, 14)} years old and their flat number is "
                         f"{rng.randint(10, 99)}.")
    rng.shuffle(parts)
    return {"cat": "extract", "type": "json", "expect": ages,
            "prompt": " ".join(parts) + "\n\nIt is 2026. Give every person's current age as a JSON object "
                                        "{\"Full Name\": age} with exactly these people as keys. Reply with the JSON only."}


# ------------------------------------------------------------------ instructions
def h_acrostic(rng, level):
    """Lines whose first letters spell a word; exact words per line from level 2; a banned letter from level 4."""
    word = rng.choice(["solar", "river", "planet", "market", "silent", "garden", "winter", "candle", "harbour",
                       "lantern"])[: 3 + level]
    e = {"acrostic": word, "lines": len(word), "plain": True}
    rules = [f"exactly {len(word)} lines", f"the first letters of the lines spell '{word.upper()}'"]
    if level >= 2:
        e["line_words"] = rng.randint(4, 7)
        rules.append(f"every line has exactly {e['line_words']} words")
    if level >= 4:
        banned = rng.choice([c for c in "eaiot" if c not in word])
        e["forbid"] = banned
        rules.append(f"the letter '{banned}' never appears (upper or lower case)")
    return {"cat": "instruct", "type": "rules", "expect": e,
            "prompt": f"Write a short poem about {rng.choice(['the sea', 'a city at night', 'autumn', 'a train'])}: "
                      + "; ".join(rules) + ". No title, no numbering, nothing else."}


def h_sortmix(rng, level):
    """Sort a longer list with decimals and negatives; duplicates removed from level 4."""
    n = 8 * level
    nums = [round(rng.uniform(-500, 500), rng.choice([0, 1, 2])) if level >= 3 else rng.randint(0, 9999)
            for _ in range(n)]
    nums = [int(x) if float(x).is_integer() else x for x in nums]
    if level >= 4:
        nums += rng.sample(nums, 3)
        rng.shuffle(nums)
    want = sorted(set(nums) if level >= 4 else nums)
    rule = "remove duplicates, then sort from smallest to largest" if level >= 4 else "sort from smallest to largest"
    return {"cat": "instruct", "type": "exact", "expect": {"value": ", ".join(map(str, want))},
            "prompt": f"{rule.capitalize()} and reply with the numbers separated by ', ' only, written exactly as "
                      f"given: {', '.join(map(str, nums))}"}


def h_transform(rng, level):
    """Several string operations in a row; each level adds one."""
    words = [_word(rng, rng.randint(2, 3)) for _ in range(4 + level)]
    steps = [("reverse the order of the words", lambda ws: ws[::-1]),
             ("write every second word (the 2nd, 4th, …) in UPPERCASE", lambda ws: [w.upper() if i % 2 else w
                                                                                   for i, w in enumerate(ws)]),
             ("reverse the letters inside every word", lambda ws: [w[::-1] for w in ws]),
             ("drop the first letter of every word", lambda ws: [w[1:] for w in ws]),
             ("move the last word to the front", lambda ws: ws[-1:] + ws[:-1])]
    chosen = rng.sample(steps, level)
    ws = words[:]
    for _t, fn in chosen:
        ws = fn(ws)
    return {"cat": "instruct", "type": "exact", "expect": {"value": " ".join(ws)},
            "prompt": f"Start from: '{' '.join(words)}'. Apply these steps in this order: "
                      + "; then ".join(t for t, _f in chosen) + ". Reply with the result only, without quotes."}


FAMILIES = [h_chain, h_money, h_base, h_order, h_houses, h_count, h_workdays, h_code_rpn, h_code_wrap, h_code_cover,
            h_people, h_acrostic, h_sortmix, h_transform]
MAX_LEVEL = 5


def family(g):
    return g.__name__[2:]
