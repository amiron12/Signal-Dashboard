import json
import sqlite3
from datetime import datetime
from pathlib import Path

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


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


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


def get_history(
    company: str, receiver: str | None = None, since: datetime | None = None
) -> list[SignalEvent]:
    conn = _connect()
    try:
        query = "SELECT receiver, company, target_url, timestamp, status, signals, error_message FROM events WHERE company = ?"
        params: list = [company]

        if receiver is not None:
            query += " AND receiver = ?"
            params.append(receiver)
        if since is not None:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

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
