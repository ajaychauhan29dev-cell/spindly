from database import db
from database.queries import get_category_breakdown


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


def test_seeded_user_breakdown(seeded_db):
    result = get_category_breakdown(seeded_db)
    assert len(result) == 7
    amounts = [item["amount"] for item in result]
    assert amounts == sorted(amounts, reverse=True)
    assert result[0]["name"] == "Bills"
    assert result[0]["amount"] == 120.0
    assert all(isinstance(item["pct"], int) for item in result)
    assert sum(item["pct"] for item in result) == 100


def test_empty_user_returns_empty_list(empty_user):
    assert get_category_breakdown(empty_user) == []


def test_single_category_is_100_pct(empty_user):
    _add_expenses(empty_user, [(10.0, "Food"), (5.5, "Food")])
    assert get_category_breakdown(empty_user) == [
        {"name": "Food", "amount": 15.5, "pct": 100}
    ]


def test_three_way_tie_sums_to_100(empty_user):
    _add_expenses(empty_user, [(10.0, "Food"), (10.0, "Bills"), (10.0, "Travel")])
    result = get_category_breakdown(empty_user)
    assert [item["name"] for item in result] == ["Bills", "Food", "Travel"]
    assert [item["pct"] for item in result] == [34, 33, 33]
    assert sum(item["pct"] for item in result) == 100


def test_other_users_expenses_do_not_leak(empty_user):
    other_id = db.create_user("Other", "other@example.com", "secret123")
    _add_expenses(empty_user, [(20.0, "Food")])
    _add_expenses(other_id, [(500.0, "Shopping"), (30.0, "Food")])
    assert get_category_breakdown(empty_user) == [
        {"name": "Food", "amount": 20.0, "pct": 100}
    ]
