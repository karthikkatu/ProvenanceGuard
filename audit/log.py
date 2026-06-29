"""
Structured audit log — SQLite backend.

One row per submission, keyed on content_id.
Milestone 5 adds an appeals table to the same database.
"""

import os
import sqlite3
from typing import List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.db")

# Columns this version of the schema requires.
_REQUIRED_COLUMNS = {"content_id", "llm_score", "attribution", "confidence", "timestamp"}


def init_db() -> None:
    """Create the submissions table. Recreates it if the schema is outdated."""
    with _connect() as conn:
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(submissions)")
        }
        if existing_columns and not _REQUIRED_COLUMNS.issubset(existing_columns):
            conn.execute("DROP TABLE IF EXISTS submissions")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id      TEXT    NOT NULL UNIQUE,
                creator_id      TEXT    NOT NULL,
                text            TEXT    NOT NULL,
                llm_score       REAL    NOT NULL,
                llm_reason      TEXT    NOT NULL,
                attribution     TEXT    NOT NULL,
                confidence      REAL    NOT NULL,
                label_text      TEXT    NOT NULL,
                status          TEXT    NOT NULL,
                timestamp       TEXT    NOT NULL
            )
        """)


def write_submission(entry: dict) -> None:
    """Append one audit row. Raises on missing required keys."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO submissions (
                content_id, creator_id, text,
                llm_score, llm_reason,
                attribution, confidence, label_text,
                status, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["content_id"],
            entry["creator_id"],
            entry["text"],
            entry["llm_score"],
            entry["llm_reason"],
            entry["attribution"],
            entry["confidence"],
            entry["label_text"],
            entry["status"],
            entry["timestamp"],
        ))


def get_log() -> List[dict]:
    """Return all submissions, newest first."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent(limit: int = 10) -> List[dict]:
    """Return the most recent `limit` submissions as plain dicts."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)
