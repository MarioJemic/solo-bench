# solo-bench

An adaptive, hard-to-memorise exam for language models **and** whole AI systems (Claude Code, Codex, your own agent),
from Solo — a local AI orchestrator by Mario Jemic that uses it to choose models and to measure
its own progress.

* **Nothing to memorise.** 14 task families (long arithmetic, money chains, base conversion, ranking puzzles, logic
  puzzles, letter counting, working days, three programming families, extraction with traps, acrostics, sorting, string
  transformations) are generated from a random seed at run time. Graders are deterministic: no judge model.
* **It stays hard.** Every family has 15 difficulty levels (6–15 added as the best models reached 100 %; earlier levels never change). Solo raises a family's level when the best model gets 90 %
  of it, so the best stays around 75 % instead of everyone sitting at 100 %.
* **One scale.** Results are put on one ability scale (Rasch / 1-parameter IRT), also results made at different levels.
* **Models and systems.** Any OpenAI-compatible API, or any command-line system (the task goes to it on standard
  input, in an empty temporary folder).
* Python standard library only.

```bash
python -m solobench run --url https://api.openai.com/v1 --model gpt-4.1-mini --key-env OPENAI_API_KEY
python -m solobench run --cmd "claude -p --output-format json --permission-mode dontAsk" --name "Claude Code"
python -m solobench run --cmd "codex exec --skip-git-repo-check --sandbox read-only -" --name "Codex"
python -m solobench report results/*.json     # report.html: ability vs cost
```

`--levels levels.json` sets the level per family (`{"houses": 5, "chain": 4}`); the default is 3.

Running a command-line system runs that program on your computer with your account: use its read-only / no-prompt
mode, as above.

## Licence

MIT — see LICENSE.
