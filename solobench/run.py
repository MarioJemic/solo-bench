"""solo-bench: an adaptive, hard-to-memorise exam for language models and AI systems.

    python -m solobench run --url https://api.openai.com/v1 --model gpt-4.1-mini --key-env OPENAI_API_KEY
    python -m solobench run --cmd "claude -p" --name "Claude Code (sonnet)"
    python -m solobench report results/*.json            # -> report.html: ability vs cost, one scale for all

Every task is generated from a random seed at run time (14 families × 9 difficulty levels), so there is nothing to
memorise; graders are deterministic. Abilities (Rasch / 1-parameter IRT) put every result on one scale, also results
made at different levels. Python standard library only.
"""
import argparse
import json
import os
import random
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import ability
from .gen_hard import FAMILIES, MAX_LEVEL, family
from .grade import GRADERS, g_code

DEFAULT_LEVEL = 3


def tasks(seed, levels):
    out = []
    for g in FAMILIES:
        f = family(g)
        t = g(random.Random(f"{seed}:{f}"), levels.get(f, DEFAULT_LEVEL))
        t["id"] = f"hr-{f}-L{levels.get(f, DEFAULT_LEVEL)}-0"
        out.append(t)
    return out


def ask_openai(url, model, key, prompt):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
    usage = data.get("usage") or {}
    return data["choices"][0]["message"]["content"] or "", None, usage


def ask_cmd(cmd, prompt, timeout=300):
    """The task on standard input (never on the command line), in an empty temporary folder."""
    with tempfile.TemporaryDirectory(prefix="solobench-") as work:
        p = subprocess.run(shlex.split(cmd, posix=os.name != "nt"), input=prompt, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=work, timeout=timeout)
    text = p.stdout
    try:                                    # tools with JSON output (claude -p --output-format json)
        data = json.loads(text)
        if isinstance(data, dict) and "result" in data:
            return str(data["result"]), None, {"cost_usd": data.get("total_cost_usd")}
    except ValueError:
        pass
    return text, (p.stderr.strip()[-300:] if p.returncode and not text.strip() else None), {}


def grade(t, text):
    if t["type"] == "code":
        return g_code(t, text)
    return GRADERS[t["type"]](t, text)


def run(args):
    levels = json.load(open(args.levels)) if args.levels else {}
    seed = args.seed or secrets.randbits(48)
    ts = tasks(seed, levels) * args.repeat
    key = os.environ.get(args.key_env) if args.key_env else None

    def one(t):
        started = time.time()
        try:
            text, err, usage = (ask_cmd(args.cmd, t["prompt"]) if args.cmd else
                                ask_openai(args.url, args.model, key, t["prompt"]))
        except Exception as e:  # noqa: BLE001
            text, err, usage = "", f"{type(e).__name__}: {e}", {}
        score, detail = grade(t, text) if text else (0.0, err or "no answer")
        print(f"  {score:4.0%}  {t['id']:<22} {detail[:70]}", flush=True)
        return {"task": t["id"], "family": t["id"].split("-")[1], "score": score, "detail": detail,
                "seconds": round(time.time() - started, 1), "usage": usage}
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        items = list(pool.map(one, ts))
    name = args.name or args.model or args.cmd
    total = sum(i["score"] for i in items) / len(items)
    cost = sum((i["usage"] or {}).get("cost_usd") or 0 for i in items) or None
    out = {"name": name, "seed": seed, "levels": {family(g): levels.get(family(g), DEFAULT_LEVEL) for g in FAMILIES},
           "total": round(total, 3), "cost_usd": cost, "items": items, "ts": time.time(), "version": "solo-bench 1"}
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"{''.join(c if c.isalnum() else '_' for c in name)}-{int(time.time())}.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1)
    print(f"\n{name}: {total:.0%} on {len(items)} tasks" + (f", ${cost:.3f}" if cost else "") + f"  →  {path}")


def report(args):
    results = [json.load(open(p, encoding="utf-8")) for p in args.files]
    rows = [(r["name"], ability.item_key(i["task"]), i["score"]) for r in results for i in r["items"]]
    theta, b, n = ability.fit(rows)
    levels = results[-1]["levels"]
    names = {}
    for r in results:
        c = names.setdefault(r["name"], {"cost": 0.0, "tasks": 0})
        c["cost"] += r.get("cost_usd") or 0
        c["tasks"] += len(r["items"])
    pts = sorted(((m, ability.expected(theta[m], b, levels), names[m]["cost"] / max(1, names[m]["tasks"]) * 1000)
                  for m in theta), key=lambda x: -(x[1] or 0))
    w, h, left, bottom = 640, 340, 52, 40
    max_x = max([p[2] for p in pts] + [0.01]) * 1.1
    dots = "".join(f'<circle cx="{left + p[2] / max_x * (w - left - 16):.1f}" cy="{h - bottom - (p[1] or 0) * (h - 14 - bottom):.1f}" '
                   f'r="6" fill="hsl({i * 47 % 360} 65% 55%)"><title>{p[0]}: {p[1]:.0%}</title></circle>'
                   for i, p in enumerate(pts))
    table = "".join(f"<tr><td>{p[0]}</td><td>{p[1]:.0%}</td><td>{theta[p[0]]:+.2f}</td><td>${p[2]:.2f}</td><td>{n[p[0]]}</td></tr>"
                    for p in pts)
    html = f"""<!doctype html><meta charset="utf-8"><title>solo-bench report</title>
<style>body{{font:14px system-ui;margin:24px;background:#0b0b0c;color:#ececf1}}td,th{{padding:4px 10px;text-align:left}}
svg{{max-width:680px;width:100%}}</style><h2>solo-bench</h2>
<p>Expected score on the current hard exam (ability on one scale) against cost per 1,000 tasks.</p>
<svg viewBox="0 0 {w} {h}"><line x1="{left}" y1="{h - bottom}" x2="{w - 16}" y2="{h - bottom}" stroke="#666"/>
<line x1="{left}" y1="14" x2="{left}" y2="{h - bottom}" stroke="#666"/>{dots}</svg>
<table><tr><th>System / model</th><th>Expected score</th><th>Ability</th><th>Cost / 1,000 tasks</th><th>Answers</th></tr>{table}</table>"""
    open(args.html, "w", encoding="utf-8").write(html)
    print(f"{len(results)} results, {len(theta)} systems → {args.html}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="solobench", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="what", required=True)
    r = sub.add_parser("run", help="run the exam once")
    r.add_argument("--url", help="OpenAI-compatible base URL, e.g. https://api.openai.com/v1")
    r.add_argument("--model")
    r.add_argument("--key-env", help="environment variable that holds the API key")
    r.add_argument("--cmd", help="a command-line AI system; the task goes to it on standard input")
    r.add_argument("--name", help="name in the results")
    r.add_argument("--levels", help="JSON file {family: level 1-%d}" % MAX_LEVEL)
    r.add_argument("--seed", type=int)
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--parallel", type=int, default=2)
    r.add_argument("--out", default="results")
    rp = sub.add_parser("report", help="one scale and a chart from several result files")
    rp.add_argument("files", nargs="+")
    rp.add_argument("--html", default="report.html")
    a = p.parse_args(argv)
    if a.what == "run":
        if not a.cmd and not (a.url and a.model):
            p.error("give --cmd, or --url and --model")
        run(a)
    else:
        report(a)


if __name__ == "__main__":
    sys.exit(main())
