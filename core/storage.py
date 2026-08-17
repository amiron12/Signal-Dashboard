import json
import sqlite3
from pathlib import Path

from .config import load_config
from .models import SignalEvent

DB_PATH = Path("signals.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receiver TEXT NOT NULL,
    company TEXT NOT NULL,
    target_url TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    signals TEXT NOT NULL,
    error_message TEXT
);
"""

_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company_name TEXT NOT NULL,
    company_url TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    conn.execute(_SETTINGS_SCHEMA)
    return conn


def get_company() -> dict:
    """Returns {"name": ..., "url": ...}. Seeds from config.yaml's company
    section on first call, if nothing has been set via set_company() yet."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT company_name, company_url FROM settings WHERE id = 1"
        ).fetchone()
        if row is not None:
            return {"name": row[0], "url": row[1]}

        default = load_config()["company"]
        conn.execute(
            "INSERT INTO settings (id, company_name, company_url) VALUES (1, ?, ?)",
            (default["name"], default["url"]),
        )
        conn.commit()
        return {"name": default["name"], "url": default["url"]}
    finally:
        conn.close()


def set_company(name: str, url: str) -> dict:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO settings (id, company_name, company_url) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                company_name = excluded.company_name,
                company_url = excluded.company_url
            """,
            (name, url),
        )
        conn.commit()
        return {"name": name, "url": url}
    finally:
        conn.close()


def save_event(event: SignalEvent) -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO events (receiver, company, target_url, timestamp, status, signals, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.receiver,
                event.company,
                event.target_url,
                event.timestamp.isoformat(),
                event.status,
                json.dumps(event.signals),
                event.error_message,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_history(company: str, receiver: str | None = None) -> list[SignalEvent]:
    conn = _connect()
    try:
        query = "SELECT receiver, company, target_url, timestamp, status, signals, error_message FROM events WHERE company = ?"
        params: list = [company]

        if receiver is not None:
            query += " AND receiver = ?"
            params.append(receiver)

        query += " ORDER BY timestamp ASC"

        rows = conn.execute(query, params).fetchall()
        return [
            SignalEvent(
                receiver=row[0],
                company=row[1],
                target_url=row[2],
                timestamp=row[3],
                status=row[4],
                signals=json.loads(row[5]),
                error_message=row[6],
            )
            for row in rows
        ]
    finally:
        conn.close()
