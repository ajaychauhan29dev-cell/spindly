"""Read-only query helpers for the profile page. No Flask imports."""

from datetime import datetime

from database import db


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

def get_recent_transactions(user_id, limit=10):
    """Return the user's latest expenses as [{date, description, category, amount}], newest first."""
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
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

def get_summary_stats(user_id):
    """Return {total_spent, transaction_count, top_category} for the user."""
    conn = db.get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
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

def get_category_breakdown(user_id):
    """Return [{name, amount, pct}] sorted by amount DESC, name ASC.

    pct values are ints that sum to exactly 100 (remainder goes to the
    first item). Returns [] when the user has no expenses.
    """
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id,),
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
