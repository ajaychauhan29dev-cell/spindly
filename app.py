import sqlite3

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

from database.db import (  # noqa: F401
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)

app = Flask(__name__)
# Dev-only key for flash(); replace with a real secret before deploying.
app.secret_key = "spendly-dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


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

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Demo User",
        "initials": "DU",
        "email": "demo@spendly.com",
        "member_since": "January 2026",
    }
    stats = {
        "total_spent": "₹8,450.00",
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "22 Oct 2026", "description": "Weekend shopping", "category": "Shopping", "amount": "₹1,800.00"},
        {"date": "18 Oct 2026", "description": "Movie night", "category": "Entertainment", "amount": "₹600.00"},
        {"date": "15 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": "₹450.00"},
        {"date": "12 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": "₹2,400.00"},
        {"date": "08 Oct 2026", "description": "Metro card recharge", "category": "Transport", "amount": "₹500.00"},
        {"date": "03 Oct 2026", "description": "Groceries", "category": "Food", "amount": "₹1,200.00"},
    ]
    categories = [
        {"name": "Bills", "total": "₹2,400.00", "percent": 28},
        {"name": "Shopping", "total": "₹1,800.00", "percent": 21},
        {"name": "Food", "total": "₹1,200.00", "percent": 14},
        {"name": "Entertainment", "total": "₹600.00", "percent": 7},
        {"name": "Transport", "total": "₹500.00", "percent": 6},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
