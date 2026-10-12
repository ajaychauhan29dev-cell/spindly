import calendar
import math
import sqlite3
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from database import queries
from database.db import (  # noqa: F401
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)

MAX_AMOUNT = 10_000_000
MAX_DESCRIPTION_LENGTH = 200

app = Flask(__name__)
# Dev-only key for flash(); replace with a real secret before deploying.
app.secret_key = "spendly-dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


@app.template_filter("inr")
def inr(value):
    return f"₹{float(value or 0):,.2f}"


@app.template_filter("fmt_date")
def fmt_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value


def _initials(name):
    parts = (name or "").split()[:2]
    return "".join(p[0] for p in parts).upper() or "?"


def _parse_date(value):
    """Return value as a zero-padded YYYY-MM-DD string, or None if invalid."""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _resolve_date_range(args):
    """Validate date_from/date_to query args; return (date_from, date_to).

    Anything other than a valid, correctly ordered pair means "no filter".
    Only a reversed range is reported to the user; malformed or missing
    dates silently fall back to the unfiltered view.
    """
    date_from = _parse_date(args.get("date_from"))
    date_to = _parse_date(args.get("date_to"))
    if not (date_from and date_to):
        return None, None
    if date_from > date_to:
        flash("Start date must be before end date.", "error")
        return None, None
    return date_from, date_to


def _validate_expense_form(form):
    """Validate add/edit expense form values (already whitespace-stripped).

    Returns (expense_kwargs, None) on success or (None, error_message) on the
    first failure. The kwargs keys (notably expense_date) match the parameters
    of both queries.insert_expense and queries.update_expense.
    """
    if not form["amount"]:
        return None, "Amount is required."
    try:
        amount = float(form["amount"])
    except ValueError:
        return None, "Amount must be a number."
    # float() happily parses "nan" and "inf", so they must be rejected here.
    if not math.isfinite(amount) or amount <= 0 or amount > MAX_AMOUNT:
        return None, f"Amount must be between 0.01 and {MAX_AMOUNT:,}."

    if form["category"] not in queries.CATEGORIES:
        return None, "Please choose a valid category."

    expense_date = _parse_date(form["date"])
    if expense_date is None:
        return None, "Please enter a valid date."

    description = form["description"]
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return None, (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )

    return {
        "amount": round(amount, 2),
        "category": form["category"],
        "expense_date": expense_date,
        "description": description or None,
    }, None


def _months_ago(today, months):
    """Return the date `months` calendar months before today (day clamped)."""
    index = today.year * 12 + today.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _build_presets(today):
    """Return the quick-select filter presets with their date ranges."""
    end = today.isoformat()
    return [
        {
            "key": "this_month",
            "label": "This Month",
            "date_from": today.replace(day=1).isoformat(),
            "date_to": end,
        },
        {
            "key": "last_3_months",
            "label": "Last 3 Months",
            "date_from": _months_ago(today, 3).isoformat(),
            "date_to": end,
        },
        {
            "key": "last_6_months",
            "label": "Last 6 Months",
            "date_from": _months_ago(today, 6).isoformat(),
            "date_to": end,
        },
        {"key": "all_time", "label": "All Time", "date_from": None, "date_to": None},
    ]


def _active_preset(presets, date_from, date_to):
    """Return the matching preset key, or "custom" for an unmatched range."""
    for preset in presets:
        if (preset["date_from"], preset["date_to"]) == (date_from, date_to):
            return preset["key"]
    return "custom"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    error = None
    if not (name and email and password and confirm_password):
        error = "All fields are required."
    elif password != confirm_password:
        error = "Passwords do not match."
    else:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "Email already registered."

    if error:
        flash(error, "error")
        return render_template("register.html", name=name, email=email)

    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email and password else None
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html", email=email)

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = queries.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    user["initials"] = _initials(user["name"])

    date_from, date_to = _resolve_date_range(request.args)
    presets = _build_presets(date.today())

    return render_template(
        "profile.html",
        user=user,
        stats=queries.get_summary_stats(user_id, date_from, date_to),
        transactions=queries.get_recent_transactions(
            user_id, date_from=date_from, date_to=date_to
        ),
        categories=queries.get_category_breakdown(user_id, date_from, date_to),
        presets=presets,
        active_preset=_active_preset(presets, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    form = {
        "amount": "",
        "category": "",
        "date": date.today().isoformat(),
        "description": "",
    }
    if request.method == "POST":
        form = {key: request.form.get(key, "").strip() for key in form}
        expense, error = _validate_expense_form(form)
        if not error:
            queries.insert_expense(user_id, **expense)
            flash("Expense added.", "success")
            return redirect(url_for("profile"))
        flash(error, "error")

    return render_template(
        "add_expense.html",
        categories=queries.CATEGORIES,
        form=form,
        max_description=MAX_DESCRIPTION_LENGTH,
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    expense = queries.get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    form = {
        "amount": f"{expense['amount']:.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    if request.method == "POST":
        form = {key: request.form.get(key, "").strip() for key in form}
        values, error = _validate_expense_form(form)
        if not error:
            if not queries.update_expense(id, user_id, **values):
                abort(404)
            flash("Expense updated.", "success")
            return redirect(url_for("profile"))
        flash(error, "error")

    return render_template(
        "edit_expense.html",
        categories=queries.CATEGORIES,
        form=form,
        expense_id=id,
        max_description=MAX_DESCRIPTION_LENGTH,
    )


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
