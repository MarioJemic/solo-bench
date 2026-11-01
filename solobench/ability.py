"""Ability on one scale (Rasch / 1-parameter IRT): every model gets an ability θ, every kind of task a difficulty b,
and the chance of a right answer is σ(θ − b). Fitted together on ALL exam answers ever given (basic and hard, every
level), so models stay comparable when the hard exam gets harder: a new level is just a new, more difficult item.

Shown as the "expected score on the current hard exam": the average of σ(θ − b) over the hard families at their
current levels — the same yardstick for every model, also for models measured on older levels.
Partial credit (code tests, JSON fields) counts as a fraction of a right answer.
"""
import math
import re

HARD_ID = re.compile(r"^h[xr]-(\w+)-L(\d+)-")             # levels 10-15 have two digits
BASIC_ID = re.compile(r"^(?:fx|rnd)-(.+?)-\d+$")
PRIOR_THETA, PRIOR_B = 2.5, 3.0          # standard deviations of the priors (keep perfect scores finite)
LEVEL_STEP = 1.0                          # assumed extra difficulty per level where a level has no data yet


def item_key(task_id):
    if (task_id or "").startswith("pub-"):                # a public test is one family (its questions vary)
        return "pub:" + task_id.split("-")[1]
    m = HARD_ID.match(task_id or "")
    if m:
        return f"{m.group(1)}@{m.group(2)}"
    m = BASIC_ID.match(task_id or "")
    return f"basic:{m.group(1)}" if m else f"basic:{task_id}"


def _sig(x):
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, x))))


def fit(rows, rounds=60):
    """rows: (model, item key, score 0..1). -> (theta {model: θ}, b {key: b}, n {model: answers})."""
    cells = {}
    for m, k, y in rows:
        c = cells.setdefault((m, k), [0.0, 0])
        c[0] += y
        c[1] += 1
    models = sorted({m for m, _k in cells})
    keys = sorted({k for _m, k in cells})
    theta, b = dict.fromkeys(models, 0.0), dict.fromkeys(keys, 0.0)
    by_m, by_k = {}, {}
    for (m, k), c in cells.items():
        by_m.setdefault(m, []).append((k, *c))
        by_k.setdefault(k, []).append((m, *c))
    for _ in range(rounds):                   # alternating Newton steps with Gaussian priors (MAP)
        for m in models:
            g, h = -theta[m] / PRIOR_THETA ** 2, 1 / PRIOR_THETA ** 2
            for k, y, n in by_m[m]:
                p = _sig(theta[m] - b[k])
                g += y - n * p
                h += n * p * (1 - p)
            theta[m] += max(-1.0, min(1.0, g / h))
        for k in keys:
            g, h = -b[k] / PRIOR_B ** 2, 1 / PRIOR_B ** 2
            for m, y, n in by_k[k]:
                p = _sig(theta[m] - b[k])
                g -= y - n * p
                h += n * p * (1 - p)
            b[k] += max(-1.0, min(1.0, g / h))
    return theta, b, {m: sum(n for _k, _y, n in by_m[m]) for m in models}


def difficulty(b, fam, level):
    """b of a family at a level; a level without data: the nearest measured level ± LEVEL_STEP per level."""
    if f"{fam}@{level}" in b:
        return b[f"{fam}@{level}"]
    known = [(int(k.split("@")[1]), v) for k, v in b.items() if k.startswith(fam + "@")]
    if not known:
        return None
    lv, v = min(known, key=lambda x: abs(x[0] - level))
    return v + LEVEL_STEP * (level - lv)


def expected(theta, b, levels):
    """Expected share right on the current hard exam (families at their current levels)."""
    ds = [d for d in (difficulty(b, f, lv) for f, lv in levels.items()) if d is not None]
    return round(sum(_sig(theta - d) for d in ds) / len(ds), 3) if ds else None
