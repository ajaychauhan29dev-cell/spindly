# Plan: 01 — Database Setup

## Context

Spendly's `database/db.py` is a 5-line comment stub, and `app.py` has no DB wiring. Every later step (auth, profile, expenses) depends on a working SQLite data layer, so this step implements `get_db()`, `init_db()` and `seed_db()` and calls them on app startup. No new routes and no new packages.

Source spec: `.claude/specs/01-database-setup-empty.md`. The requested name `01-database-setup.md` doesn't exist, so the `-empty` file was used.

## Decisions

- **DB file:** `expense_tracker.db` in the project root. It is already in `.gitignore`, and the spec allows it.
- **Path:** `DB_PATH` is built from `db.py`'s own location (`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`), so it doesn't depend on the CWD.
- **`get_db()`:** returns a plain `sqlite3.Connection` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON` on every call. It does no Flask `g` or teardown handling yet. `init_db()` and `seed_db()` open their own connection and close it in `try/finally`.
- **Seed dates:** built from `date.today()` with fixed days 1–22 (always valid in any month), formatted `YYYY-MM-DD`.
- **`app.py` import:** `from database.db import get_db, init_db, seed_db  # noqa: F401`. The spec requires the import, and `get_db` is unused for now.
- **Tests:** add `tests/test_db.py` (optional, pytest is already in `requirements.txt`). It monkeypatches `db.DB_PATH` to a `tmp_path` file so the real DB isn't touched.

## Changes

### `database/db.py` (replace the stub)
- Imports: `os`, `sqlite3`, `date` from `datetime`, `generate_password_hash` from `werkzeug.security`.
- `get_db()`: connect to `DB_PATH`, set `row_factory`, run `PRAGMA foreign_keys = ON`, return.
- `init_db()`: two `CREATE TABLE IF NOT EXISTS` statements, then commit and close.
  - `users`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `name TEXT NOT NULL`, `email TEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`, `created_at TEXT DEFAULT (datetime('now'))`.
  - `expenses`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `user_id INTEGER NOT NULL REFERENCES users(id)`, `amount REAL NOT NULL`, `category TEXT NOT NULL`, `date TEXT NOT NULL`, `description TEXT`, `created_at TEXT DEFAULT (datetime('now'))`.
  - The `datetime('now')` default is wrapped in parentheses, because SQLite requires that for expression defaults.
- `seed_db()`:
  1. `SELECT COUNT(*) FROM users`. If above 0, close and return.
  2. `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)` with `generate_password_hash("demo123")`. Take `cur.lastrowid` as the user id.
  3. `executemany("INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)", rows)`.
  4. Commit and close.

### `app.py`
- Add the import after line 1.
- After `app = Flask(__name__)`:
  ```python
  with app.app_context():
      init_db()
      seed_db()
  ```
- Routes and `app.run(debug=True, port=5001)` stay unchanged.
- Setup runs at import time (also under pytest-flask and the reloader). That's harmless because both functions are idempotent.

### `tests/test_db.py` (new, optional)
Covers: tables exist, one user, 8 expenses, all 7 categories present, hashed password verifies, a second `seed_db()` adds nothing, FK violation raises `IntegrityError`, duplicate email raises `IntegrityError`.

## Seed data

Demo user: `Demo User` / `demo@spendly.com` / `demo123` (stored hashed). `Date` is the day of the current month.

| # | Amount | Category | Date | Description |
|---|---|---|---|---|
| 1 | 12.50 | Food | 01 | Lunch at cafe |
| 2 | 45.00 | Transport | 03 | Monthly bus pass top-up |
| 3 | 120.00 | Bills | 05 | Electricity bill |
| 4 | 30.00 | Health | 08 | Pharmacy |
| 5 | 25.00 | Entertainment | 12 | Movie tickets |
| 6 | 79.99 | Shopping | 15 | New shoes |
| 7 | 15.00 | Other | 18 | Miscellaneous |
| 8 | 38.75 | Food | 22 | Weekly groceries |

Seven categories across eight rows means Food repeats.

## Verification (maps to the spec's Definition of Done)

Run from a directory other than the project root, to confirm the path handling.

1. **File and schema:** start the app. `expense_tracker.db` appears in the project root. `sqlite3 expense_tracker.db ".schema"` matches the spec.
2. **Seed:** 1 user, 8 expenses, 7 distinct categories, all dates in the current month. `password_hash` is not plaintext, and `check_password_hash` accepts `demo123`.
3. **Idempotent:** restart or re-import twice. The counts stay at 1 user and 8 expenses, with no errors.
4. **Foreign keys:** `PRAGMA foreign_keys` returns 1 on a `get_db()` connection. An expense with `user_id=999` raises `sqlite3.IntegrityError`.
5. **Row factory and uniqueness:** `row["email"]` works. A duplicate email raises `IntegrityError`.
6. **No regression:** the app still serves on port 5001, and `/` and `/login` return 200. `git status` shows only `database/db.py`, `app.py` and `tests/test_db.py`.
7. **Style and constraints:** PEP8, every query parameterized, no new packages. `pytest` passes.
8. **Per CLAUDE.md:** have a subagent verify the test results after implementation.

## Notes
- `.gitignore` already ignores `.claude/plans/`, so this plan won't be committed.
- Plan mode only allows editing this file. After approval, copy it to `.claude/plans/01-database-setup.md` as requested.
