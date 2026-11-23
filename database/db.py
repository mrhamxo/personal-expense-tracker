import calendar
import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) "
            "VALUES (?, ?, ?)",
            (
                "Demo User",
                "demo@spendly.com",
                generate_password_hash("demo123"),
            ),
        )
        user_id = cursor.lastrowid

        today = date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        samples = [
            (CATEGORIES[0], 450.00, 1, "Groceries"),
            (CATEGORIES[1], 120.50, 3, "Bus fare"),
            (CATEGORIES[2], 2500.00, 6, "Electricity bill"),
            (CATEGORIES[3], 800.00, 9, "Pharmacy"),
            (CATEGORIES[4], 600.00, 12, "Movie night"),
            (CATEGORIES[5], 1500.00, 16, "New shirt"),
            (CATEGORIES[6], 200.00, 20, "Miscellaneous"),
            (CATEGORIES[0], 350.75, 25, "Dinner out"),
        ]
        rows = [
            (
                user_id,
                amount,
                category,
                date(today.year, today.month, min(day, last_day)).isoformat(),
                description,
            )
            for category, amount, day, description in samples
        ]
        conn.executemany(
            "INSERT INTO expenses "
            "(user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
