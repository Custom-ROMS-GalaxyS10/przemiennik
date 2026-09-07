from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
import config
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
DATA_FILE = os.path.join(BASE_DIR, "data", "przemienniki.json")


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            znak TEXT UNIQUE NOT NULL,
            haslo TEXT NOT NULL,
            data_rejestracji TEXT NOT NULL,
            admin INTEGER DEFAULT 0
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS zgloszenia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            przemiennik_id INTEGER NOT NULL,
            tresc TEXT NOT NULL,
            data TEXT NOT NULL,
            status TEXT DEFAULT 'nowe'
        )
    """)

    db.commit()

    admin = db.execute(
        "SELECT id FROM users WHERE znak = ?",
        ("ADMIN",)
    ).fetchone()

    if not admin:
        db.execute(
            """
            INSERT INTO users
            (znak, haslo, data_rejestracji, admin)
            VALUES (?, ?, ?, ?)
            """,
            (
                "ADMIN",
                generate_password_hash("admin123"),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                1
            )
        )
        db.commit()

    db.close()


def load_repeaters():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        db = get_db()

        user = db.execute(
            "SELECT admin FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        db.close()

        if not user or user["admin"] != 1:
            return "Brak dostępu", 403

        return function(*args, **kwargs)

    return wrapper


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        znak = request.form.get("znak", "").strip().upper()
        haslo = request.form.get("haslo", "")

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE znak = ?",
            (znak,)
        ).fetchone()

        db.close()

        if user and check_password_hash(user["haslo"], haslo):

            session["user_id"] = user["id"]
            session["znak"] = user["znak"]

            if user["admin"] == 1:
                return redirect(url_for("admin"))

            return redirect(url_for("index"))

        flash("Nieprawidłowy znak lub hasło.")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        znak = request.form.get("znak", "").strip().upper()
        haslo = request.form.get("haslo", "")
        haslo2 = request.form.get("haslo2", "")

        if not znak or not haslo:
            flash("Wypełnij wszystkie pola.")
            return render_template("register.html")

        if haslo != haslo2:
            flash("Hasła nie są takie same.")
            return render_template("register.html")

        db = get_db()

        existing = db.execute(
            "SELECT id FROM users WHERE znak = ?",
            (znak,)
        ).fetchone()

        if existing:
            db.close()
            flash("Ten znak jest już zarejestrowany.")
            return render_template("register.html")

        db.execute(
            """
            INSERT INTO users
            (znak, haslo, data_rejestracji)
            VALUES (?, ?, ?)
            """,
            (
                znak,
                generate_password_hash(haslo),
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        db.commit()
        db.close()

        flash("Konto zostało utworzone.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/zgloszenie", methods=["GET", "POST"])
@login_required
def zgloszenie():

    if request.method == "POST":

        przemiennik_id = request.form.get("przemiennik_id", "").strip()
        tresc = request.form.get("tresc", "").strip()

        if not przemiennik_id or not tresc:
            flash("Wypełnij wszystkie pola.")
            return render_template("zgloszenie.html")

        db = get_db()

        db.execute(
            """
            INSERT INTO zgloszenia
            (user_id, przemiennik_id, tresc, data, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                int(przemiennik_id),
                tresc,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                "nowe"
            )
        )

        db.commit()
        db.close()

        flash("Zgłoszenie zostało wysłane.")
        return redirect(url_for("index"))

    return render_template("zgloszenie.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/przemienniki")
@login_required
def przemienniki():

    lista = load_repeaters()

    return render_template(
        "przemienniki.html",
        przemienniki=lista
    )


@app.route("/przemiennik/<int:repeater_id>")
@login_required
def przemiennik(repeater_id):

    lista = load_repeaters()

    przemiennik = next(
        (p for p in lista if p["id"] == repeater_id),
        None
    )

    if not przemiennik:
        return "Nie znaleziono przemiennika", 404

    return render_template(
        "przemiennik.html",
        przemiennik=przemiennik
    )


@app.route("/profil")
@login_required
def profil():

    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    db.close()

    return render_template(
        "profil.html",
        user=user
    )


@app.route("/admin")
@admin_required
def admin():
    
    
    db = get_db()

    users = db.execute(
        "SELECT id, znak, data_rejestracji, admin FROM users"
    ).fetchall()

    db.close()

    return render_template(
        "admin.html",
        users=users
    )


@app.route("/admin/przemienniki")
@admin_required
def admin_przemienniki():
    return render_template("admin_przemienniki.html")


@app.route("/admin/uzytkownicy")
@admin_required
def admin_uzytkownicy():

    db = get_db()

    users = db.execute(
        "SELECT id, znak, data_rejestracji, admin FROM users"
    ).fetchall()

    db.close()

    return render_template(
        "admin_uzytkownicy.html",
        users=users
    )


@app.route("/admin/zgloszenia")
@admin_required
def admin_zgloszenia():

    db = get_db()

    zgloszenia = db.execute(
        """
        SELECT zgloszenia.*, users.znak
        FROM zgloszenia
        LEFT JOIN users ON users.id = zgloszenia.user_id
        ORDER BY zgloszenia.id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin_zgloszenia.html",
        zgloszenia=zgloszenia
    )




if __name__ == "__main__":

    init_db()

    print()
    print("================================")
    print(" PRZEMIENNIKI WARMIA-MAZURY")
    print("================================")
    print()
    print("Serwer LAN:")
    print(f"Adres: http://{config.HOST}:{config.PORT}")
    print()
    print("Konto administratora:")
    print(f"ZNAK: {config.ADMIN_ZNAK}")
    print(f"HASŁO: {config.ADMIN_HASLO}")
    print()

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=True
    )