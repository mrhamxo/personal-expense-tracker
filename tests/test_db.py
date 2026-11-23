import re
import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash

from database import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def _columns(table):
    conn = db.get_db()
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    finally:
        conn.close()
    return {row["name"]: row for row in rows}


def test_users_schema(temp_db):
    cols = _columns("users")
    assert set(cols) == {
        "id", "name", "email", "password_hash", "created_at"
    }
    assert cols["id"]["pk"] == 1
    assert cols["name"]["notnull"] == 1
    assert cols["email"]["notnull"] == 1
    assert cols["password_hash"]["notnull"] == 1


def test_expenses_schema(temp_db):
    cols = _columns("expenses")
    assert set(cols) == {
        "id", "user_id", "amount", "category", "date",
        "description", "created_at",
    }
    assert cols["user_id"]["notnull"] == 1
    assert cols["amount"]["type"] == "REAL"
    assert cols["description"]["notnull"] == 0

    conn = db.get_db()
    try:
        fks = conn.execute("PRAGMA foreign_key_list(expenses)").fetchall()
    finally:
        conn.close()
    assert [(fk["table"], fk["from"]) for fk in fks] == [("users", "user_id")]


def test_get_db_settings(temp_db):
    conn = db.get_db()
    try:
        assert conn.row_factory is sqlite3.Row
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_init_db_idempotent(temp_db):
    db.init_db()
    db.init_db()
    assert set(_columns("users"))


def test_unique_email(temp_db):
    conn = db.get_db()
    try:
        sql = (
            "INSERT INTO users (name, email, password_hash) "
            "VALUES (?, ?, ?)"
        )
        conn.execute(sql, ("A", "a@example.com", "x"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, ("B", "a@example.com", "y"))
    finally:
        conn.close()


def test_foreign_key_enforced(temp_db):
    conn = db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) "
                "VALUES (?, ?, ?, ?)",
                (999, 10.0, "Food", "2026-01-01"),
            )
    finally:
        conn.close()


def test_seed_counts_and_categories(temp_db):
    db.seed_db()
    conn = db.get_db()
    try:
        users = conn.execute("SELECT * FROM users").fetchall()
        expenses = conn.execute("SELECT * FROM expenses").fetchall()
    finally:
        conn.close()

    assert len(users) == 1
    assert len(expenses) == 8
    assert {e["user_id"] for e in expenses} == {users[0]["id"]}

    categories = [e["category"] for e in expenses]
    assert set(categories) == set(db.CATEGORIES)
    assert len(categories) - len(set(categories)) == 1


def test_seed_dates_current_month(temp_db):
    db.seed_db()
    conn = db.get_db()
    try:
        dates = [r["date"] for r in conn.execute("SELECT date FROM expenses")]
    finally:
        conn.close()

    prefix = date.today().strftime("%Y-%m")
    for value in dates:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        assert value.startswith(prefix)


def test_seed_password_hashed(temp_db):
    db.seed_db()
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT email, password_hash FROM users"
        ).fetchone()
    finally:
        conn.close()

    assert row["email"] == "demo@spendly.com"
    assert row["password_hash"] != "demo123"
    assert check_password_hash(row["password_hash"], "demo123")


def test_seed_idempotent(temp_db):
    db.seed_db()
    db.seed_db()
    conn = db.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 8
        )
    finally:
        conn.close()


def test_seed_skips_when_users_exist(temp_db):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) "
            "VALUES (?, ?, ?)",
            ("Existing", "e@example.com", "x"),
        )
        conn.commit()
    finally:
        conn.close()

    db.seed_db()
    conn = db.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 0
        )
    finally:
        conn.close()
