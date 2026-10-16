---
name: verify-spendly
description: Verify a Spendly change end to end — tests, health endpoint, smoke check and a browser look at the affected page. Use after any implementation, and as the stop condition for /goal loops.
---

# Verify Spendly

Encodes what "done" means so loops can check their own work. Run every step in
order; if any step fails, fix the cause and restart from step 1.

1. **Tests** — run `pytest -q`. Required: 0 failures, 0 errors.
2. **Server** — start the app with `preview_start` (never Bash). Check
   `preview_logs` for tracebacks on startup.
3. **Health** — `GET /health` must return 200 with `{"status": "ok"}`.
4. **Smoke** — `python scripts/smoke_check.py http://localhost:<port>` must
   exit 0 (health plus the public pages).
5. **Browser** — open the page the change touches, check the console is free of
   errors (`read_console_messages`), and exercise the changed interaction.
6. **Conventions** (CLAUDE.md) — no DB logic in routes, parameterized SQL, no
   new pip packages, `url_for()` in templates, port 5001 unchanged.

Report each step as PASS/FAIL with the evidence (test count, status code).
Never claim success without having run the step.
