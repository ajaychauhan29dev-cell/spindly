# Loops for Spendly

Four loop types from Anthropic's "Getting started with loops", each mapped to a
real Spendly job. Start with the simplest one that fits.

| Type | Trigger | Stops when | Spendly use |
| --- | --- | --- | --- |
| Turn-based | your prompt | Claude finishes | Build a feature; `verify-spendly` skill checks it |
| Goal-based | `/goal` | condition met or turn cap | Raise test coverage, fix all failing tests |
| Time-based | `/loop`, `/schedule` | you cancel / work done | Watch production health, watch a PR |
| Proactive | schedule/event | each task's goal met | Weekly dependency + security sweep |

## 1. Turn-based — verification skill

Prompt: `Add a monthly budget field to the profile page, then run /verify-spendly`

The skill in `.claude/skills/verify-spendly/SKILL.md` turns "does it work?" into
repeatable steps (tests, `/health`, smoke script, browser check).

## 2. Goal-based — `/goal`

Use deterministic exit criteria and a turn cap:

```
/goal pytest passes with 0 failures and every route in app.py has at least one test in tests/. Run /verify-spendly before stopping. Stop after 8 turns.
```

```
/goal GET /health returns status ok locally and `python scripts/smoke_check.py` exits 0. Stop after 5 turns.
```

## 3. Time-based — `/loop` (local) and `/schedule` (cloud)

Watch production (cheap: the script does the checking, the model only reacts):

```
/loop 15m run `python scripts/smoke_check.py https://spendly-production-c144.up.railway.app`; if anything fails, check Railway logs, diagnose, and report. Do nothing if all pass.
```

Babysit a PR:

```
/loop 5m check my PR, address review comments, and fix failing CI
```

Move it to the cloud so it survives closing your laptop:

```
/schedule every hour: run the production smoke check against the live URL and open an issue if /health is not ok
```

## 4. Proactive — routines

```
/schedule every Monday 09:00: run pytest; check requirements.txt pins for known CVEs and newer patch versions; if tests still pass after bumping a patch version, open a PR. Never bump majors. Do not merge.
```

## Cost controls

- Poll no faster than the system changes (production health: 15m, not 1m).
- Put deterministic work in `scripts/` so the model is not re-reasoning it.
- Always give `/goal` a turn cap and a measurable condition.
- Use a smaller model for routine routines; keep the best model for judgment.
- Pilot on one task, then check `/usage` before widening.
