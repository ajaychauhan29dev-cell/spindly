# Loops for Spendly

This document describes how to use Claude Code loops safely in Spendly.

## The four layers

| Mechanism       | Purpose                           | Example                          |
| --------------- | --------------------------------- | -------------------------------- |
| `CLAUDE.md`     | Persistent project rules          | Flask, SQLite, parameterized SQL |
| `/loop-feature` | Reusable implementation procedure | Implement, test, repair, review  |
| `/goal`         | Bounded completion objective      | Make the date-filter tests pass  |
| `/loop`         | Recurring scheduled work          | Check CI every five minutes      |

Hooks and scripts provide deterministic automation. They complement
these mechanisms; they do not replace acceptance criteria or tests.

## 1. Turn-based implementation

Use `/loop-feature` for a normal feature or bug fix.

Examples:

    /loop-feature 07-add-expense

    /loop-feature Fix incorrect totals on the analytics page.

The skill inspects the repository, records baseline test results,
implements a bounded change, verifies the behavior, repairs failures,
and produces a final report.

It must not commit, push, merge, or deploy.

## 2. Goal-based implementation

Use `/goal` when your Claude Code version supports it and the task
needs multiple turns to reach a measurable completion condition.

Example:

    /goal Implement spec 07-add-expense using /loop-feature. The full
    pytest suite must pass, the acceptance criteria in the spec must
    be satisfied, and applicable smoke checks must pass. Stop after
    8 turns and report any remaining failures.

Another example:

    /goal Diagnose the failing date-filter tests, fix the root cause,
    and run the full test suite. Stop after 5 turns.

Rules:

- Always define an observable success condition.
- Always set a turn cap.
- Preserve baseline failures as baseline failures.
- Do not weaken tests to make the objective pass.
- Report blockers instead of looping without progress.

A goal is an orchestration mechanism, not proof of correctness.
Actual command results determine whether verification succeeded.

## 3. Time-based loops

Use `/loop` for a task that should be repeated periodically, not
for repeatedly re-implementing the same feature.

For example, to check CI:

    /loop 5m Check the CI status for my Spendly feature branch.
    Report new failures and their relevant diagnostics. Do not push,
    merge, or modify branch protection.

For a production health check, prefer a deterministic smoke-check
script and an explicitly authorized monitoring target. Avoid frequent
polling that adds cost without useful information.

Do not automatically edit code or open/merge PRs as a side effect
of recurring monitoring unless that behavior is explicitly designed
and authorized.

Availability and exact command syntax can vary by Claude Code version.

## 4. Verification

Spendly's verification workflow is documented in:

    .claude/skills/verify-spendly/SKILL.md

Run the applicable checks:

    python -m pytest -q

    python scripts/smoke_check.py http://localhost:5001

The smoke check requires the application to be running and the
environment to be configured correctly.

Do not claim that tests, browser checks, or smoke checks passed
unless they were actually executed and passed.

## 5. Repair limits

The implementation skill permits at most five repair cycles.

Stop early when:

- All acceptance criteria and required checks pass.
- The same failure repeats without new evidence.
- Credentials or environment limitations block progress.
- Requirements need clarification.
- Further work would require a destructive or unauthorized action.

## 6. Human review and shipping

Before shipping:

- Inspect the complete diff.
- Review security-sensitive changes.
- Confirm tests and applicable verification checks pass.
- Resolve critical and high-severity review findings.
- Obtain approval for any consequential action.

The implementation loop never commits, pushes, merges, or deploys.

Use the existing review and shipping procedures only after the
implementation and verification stages are complete.

## 7. Cost controls

- Use focused tests during implementation.
- Run the full suite at the verification gate.
- Avoid repeatedly reading unrelated files.
- Do not launch parallel agents that edit the same files.
- Set turn and repair-cycle limits.
- Prefer deterministic scripts for repeatable checks.
