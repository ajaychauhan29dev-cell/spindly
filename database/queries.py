"""Read-only query helpers for the profile page. No Flask imports."""

from datetime import datetime

from database import db


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) restricting expenses to an inclusive date range.

    Both bounds are required; otherwise no filter is applied. The fragment is
    always a constant string (values are bound via `?`), so callers can safely
    concatenate it into their SQL.
    """
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


# === SECTION: USER ===

def get_user_by_id(user_id):
    """Return {name, email, member_since} for the user, or None if missing."""
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = "—"

    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


# === SECTION: TRANSACTIONS (agent 1) ===

def get_recent_transactions(user_id, limit=10, *, date_from=None, date_to=None):
    """Return the user's latest expenses (within the date range, if given) as
    [{date, description, category, amount}], newest first."""
    clause, params = _date_clause(date_from, date_to)
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ?" + clause + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# === SECTION: SUMMARY STATS (agent 2) ===

def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {total_spent, transaction_count, top_category} for the user,
    limited to the date range when both bounds are given."""
    clause, params = _date_clause(date_from, date_to)
    conn = db.get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + clause +
            " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id, *params),
        ).fetchone()
    finally:
        conn.close()

    if totals["count"] == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    return {
        "total_spent": round(totals["total"], 2),
        "transaction_count": totals["count"],
        "top_category": top["category"],
    }


# === SECTION: CATEGORY BREAKDOWN (agent 3) ===

def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return [{name, amount, pct}] sorted by amount DESC, name ASC.

    pct values are ints that sum to exactly 100 (remainder goes to the
    first item). Returns [] when the user has no expenses.
    """
    clause, params = _date_clause(date_from, date_to)
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?" + clause + " GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()

    items = [
        {"name": row["category"], "amount": round(row["total"], 2)}
        for row in rows
    ]
    grand_total = sum(item["amount"] for item in items)
    if not items or grand_total <= 0:
        return [{**item, "pct": 0} for item in items]

    for item in items:
        item["pct"] = round(item["amount"] / grand_total * 100)
    items[0]["pct"] += 100 - sum(item["pct"] for item in items)
    return items
