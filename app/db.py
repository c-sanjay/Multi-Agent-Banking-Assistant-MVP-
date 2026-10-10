"""Tiny SQLite helper. The DB plays the role of 'Enterprise Data' (layer 6)."""
import sqlite3

from app import config


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()
