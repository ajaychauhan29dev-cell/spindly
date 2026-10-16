---
name: loop-feature
description: Implement a Spendly feature through a bounded engineering loop of inspection, implementation, testing, repair, and independent verification. Use when implementing a feature from a spec or fixing a bounded bug.
argument-hint: "<spec-name or feature description>"
---

# Loop Feature — Spendly Engineering Workflow

You are the implementation orchestrator for Spendly, a Flask and SQLite
expense tracker. Follow the root CLAUDE.md and the applicable feature spec.

## Input

The user's input is available in `$ARGUMENTS`.

Accept either:

- An existing spec name, such as `07-add-expense`.
- A specific feature or bug description.

If no usable input is supplied, ask for the feature or spec name and stop.

## Non-negotiable safety rules

- Never commit, push, merge, deploy, or delete branches.
- Never modify production data or run destructive commands against a
  production database.
- Never read, print, or expose secrets from `.env` or credentials.
- Never delete or weaken tests to make verification pass.
- Never silently change the feature's acceptance criteria.
- Do not introduce packages without explicit approval.
- Preserve unrelated user changes.
- Do not claim a command passed unless it actually ran and passed.
- Ask the user when requirements are ambiguous or a consequential
  decision cannot be resolved from the spec and existing code.

## Phase 1 — Understand the task

1. Read `CLAUDE.md`.
2. If `$ARGUMENTS` identifies a spec, read
   `.claude/specs/$ARGUMENTS.md`.
3. Inspect the relevant application routes, database code, templates,
   styles, JavaScript, and tests.
4. Use the configured Explore subagent for repository exploration
   when available.
5. Identify the intended behavior and list explicit acceptance criteria.
6. Record which files are likely to change.
7. Check `git status` and preserve all pre-existing modifications.
   Never reset, stash, or discard user work without permission.

If a spec does not exist, do not invent its contents. Ask whether the
user wants to create a spec or proceed from the supplied description.

## Phase 2 — Establish the baseline

Run:

    python -m pytest -q

Record the exit code and any pre-existing failures.

If the test suite cannot run because dependencies or the environment
are unavailable, report the blocker. Do not describe the baseline as
passing.

Distinguish existing failures from regressions introduced by this task.

## Phase 3 — Plan a small change

Create a concise implementation checklist based on the acceptance
criteria.

Respect Spendly's established architecture:

- Flask routes belong in `app.py`.
- Database operations belong in `database/db.py` or the appropriate
  existing database module.
- Read-only query helpers belong in `database/queries.py` where applicable.
- Templates extend `templates/base.html`.
- Internal links use `url_for()`.
- SQL uses parameterized queries.
- Frontend JavaScript remains vanilla JavaScript.
- SQLite remains the database.
- Preserve port 5001 and existing application conventions.

Do not assume that a file or helper exists without inspecting it.

## Phase 4 — Implement

Implement the smallest coherent change that satisfies the checklist.

For each coherent change:

1. Inspect the relevant existing code.
2. Edit the necessary files.
3. Add or update tests for the intended behavior.
4. Run the most relevant focused tests.
5. Inspect the actual results before continuing.

Do not make unrelated refactors.

## Phase 5 — Verify

Use the existing verification instructions in
`.claude/skills/verify-spendly/SKILL.md`.

Run the applicable checks:

1. Focused tests for the changed behavior.
2. Full test suite:

   python -m pytest -q

3. The existing smoke check, where the application can be started safely:

   python scripts/smoke_check.py http://localhost:5001

4. Relevant route, template, database, and security checks.
5. Browser verification when a browser or preview tool is available.

Do not assume preview tools or a browser are available in every
environment. If unavailable, report the skipped check and why.

Do not run a smoke check against production unless the user explicitly
requests it. Do not alter live data to verify behavior.

## Phase 6 — Repair loop

Set MAX_REPAIR_CYCLES = 5.

A repair cycle consists of:

1. Identify a concrete failure from command output or observed behavior.
2. Find its likely root cause.
3. Make a targeted correction.
4. Rerun the failed check.
5. Rerun related regression tests.
6. Record whether the failure was resolved.

The first implementation is not counted as a repair cycle.

Never repeat an identical failed repair without new evidence.

Stop early if:

- The relevant checks pass and all acceptance criteria are satisfied.
- The same failure persists without meaningful progress.
- The environment or missing credentials block further work.
- Requirements need user clarification.
- A destructive or consequential action would be required.

Stop after five repair cycles even if failures remain.

Do not suppress failures, loosen assertions, or change acceptance
criteria just to achieve a passing result.

## Phase 7 — Independent review

When available, delegate review of the final diff to the configured
Spendly quality and security reviewer agents.

Ask them to inspect only the changes relevant to the task and report
specific findings with file and line references.

Resolve critical and high-severity findings before declaring the
feature ready.

If reviewer agents are unavailable, perform a self-review and disclose
that independent review was not completed.

Do not automatically invoke a shipping workflow or merge a PR.

## Phase 8 — Completion gate

Declare the feature VERIFIED only when:

- Every required acceptance criterion is satisfied.
- The full test suite passes.
- Applicable smoke and other required checks pass.
- No unresolved critical or high-severity findings remain.
- The final changes are consistent with CLAUDE.md.

If any required condition is unmet, report BLOCKED or NEEDS FIXES.
Never label an unverified feature as complete.

## Phase 9 — Final report

Return this report:

### Loop Feature Report

- Task:
- Spec:
- Acceptance criteria:
- Files changed:
- Baseline test result:
- Repair cycles used:
- Focused test result:
- Full test result:
- Smoke check result:
- Independent review:
- Unresolved issues:
- Manual checks still required:
- Final status: VERIFIED / NEEDS FIXES / BLOCKED

Include actual command outcomes and explain any skipped checks.

Do not commit, push, merge, or deploy.
