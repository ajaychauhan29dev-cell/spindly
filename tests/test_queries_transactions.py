from database import db
from database.queries import get_recent_transactions


def _add_expense(user_id, amount, category, date, description="test"):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


def test_seeded_user_gets_eight_rows_with_keys(seeded_db):
    result = get_recent_transactions(seeded_db)
    assert len(result) == 8
    assert set(result[0]) == {"id", "date", "description", "category", "amount"}


def test_dates_descending(seeded_db):
    dates = [t["date"] for t in get_recent_transactions(seeded_db)]
    assert dates == sorted(dates, reverse=True)
    assert len(set(dates)) == len(dates)


def test_limit_is_honoured(seeded_db):
    assert len(get_recent_transactions(seeded_db, limit=3)) == 3


def test_empty_user_returns_empty_list(empty_user):
    assert get_recent_transactions(empty_user) == []


def test_same_date_ties_break_by_newest_id(empty_user):
    _add_expense(empty_user, 1.0, "Food", "2026-01-01", "first")
    _add_expense(empty_user, 2.0, "Food", "2026-01-01", "second")
    result = get_recent_transactions(empty_user)
    assert [t["description"] for t in result] == ["second", "first"]


def test_other_users_expenses_do_not_leak(empty_user):
    other_id = db.create_user("Other", "other@example.com", "secret123")
    _add_expense(empty_user, 20.0, "Food", "2026-01-01", "mine")
    _add_expense(other_id, 500.0, "Shopping", "2026-01-02", "theirs")
    result = get_recent_transactions(empty_user)
    assert [t["description"] for t in result] == ["mine"]
