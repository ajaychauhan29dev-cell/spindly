from database import db
from database.queries import get_summary_stats


def _add_expenses(user_id, rows):
    conn = db.get_db()
    try:
        for amount, category in rows:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, "2026-01-01", "test"),
            )
        conn.commit()
    finally:
        conn.close()


def test_seeded_user_stats(seeded_db):
    assert get_summary_stats(seeded_db) == {
        "total_spent": 366.24,
        "transaction_count": 8,
        "top_category": "Bills",
    }


def test_empty_user_stats(empty_user):
    assert get_summary_stats(empty_user) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_top_category_tie_breaks_alphabetically(empty_user):
    _add_expenses(empty_user, [(10.0, "Travel"), (10.0, "Bills"), (10.0, "Food")])
    assert get_summary_stats(empty_user)["top_category"] == "Bills"


def test_other_users_expenses_do_not_leak(empty_user):
    other_id = db.create_user("Other", "other@example.com", "secret123")
    _add_expenses(empty_user, [(20.0, "Food")])
    _add_expenses(other_id, [(500.0, "Shopping")])
    assert get_summary_stats(empty_user) == {
        "total_spent": 20.0,
        "transaction_count": 1,
        "top_category": "Food",
    }
