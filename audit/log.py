"""
Structured audit log — SQLite backend.

One row per submission, keyed on content_id.
Milestone 5 adds an appeals table to the same database.
"""

import os
import sqlite3
from typing import List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.db")

# Columns this version of the schema requires.
_REQUIRED_COLUMNS = {
    "content_id", "llm_score", "attribution", "confidence",
    "stylometric_score", "timestamp",
}


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
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id          TEXT    NOT NULL UNIQUE,
                creator_id          TEXT    NOT NULL,
                text                TEXT    NOT NULL,
                llm_score           REAL    NOT NULL,
                llm_reason          TEXT    NOT NULL,
                stylometric_score   REAL    NOT NULL,
                stylometric_reason  TEXT    NOT NULL,
                attribution         TEXT    NOT NULL,
                confidence          REAL    NOT NULL,
                label_text          TEXT    NOT NULL,
                status              TEXT    NOT NULL,
                timestamp           TEXT    NOT NULL
            )
        """)

        # Appeals table — migrate if the column was previously named 'reason'.
        appeal_cols = {row[1] for row in conn.execute("PRAGMA table_info(appeals)")}
        if appeal_cols and "appeal_reasoning" not in appeal_cols:
            conn.execute("DROP TABLE IF EXISTS appeals")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                appeal_id        TEXT    NOT NULL UNIQUE,
                content_id       TEXT    NOT NULL,
                creator_id       TEXT    NOT NULL DEFAULT '',
                appeal_reasoning TEXT    NOT NULL,
                context          TEXT    NOT NULL DEFAULT '',
                status           TEXT    NOT NULL,
                timestamp        TEXT    NOT NULL
            )
        """)


def write_submission(entry: dict) -> None:
    """Append one audit row. Raises on missing required keys."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO submissions (
                content_id, creator_id, text,
                llm_score, llm_reason,
                stylometric_score, stylometric_reason,
                attribution, confidence, label_text,
                status, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["content_id"],
            entry["creator_id"],
            entry["text"],
            entry["llm_score"],
            entry["llm_reason"],
            entry["stylometric_score"],
            entry["stylometric_reason"],
            entry["attribution"],
            entry["confidence"],
            entry["label_text"],
            entry["status"],
            entry["timestamp"],
        ))


def get_log() -> List[dict]:
    """Return all submissions with appeal_status, newest first."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT
                s.*,
                EXISTS(
                    SELECT 1 FROM appeals a WHERE a.content_id = s.content_id
                ) AS appeal_status
            FROM submissions s
            ORDER BY s.id DESC
        """).fetchall()
    return [{**dict(row), "appeal_status": bool(row["appeal_status"])} for row in rows]


def get_recent(limit: int = 10) -> List[dict]:
    """Return the most recent `limit` submissions as plain dicts."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_submission(content_id: str) -> Optional[dict]:
    """Return the submission row for the given content_id, or None if not found."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM submissions WHERE content_id = ?", (content_id,)
        ).fetchone()
    return dict(row) if row else None


def update_submission_status(content_id: str, status: str) -> None:
    """Overwrite the status field on an existing submission row."""
    with _connect() as conn:
        conn.execute(
            "UPDATE submissions SET status = ? WHERE content_id = ?",
            (status, content_id),
        )


def write_appeal(entry: dict) -> None:
    """Append one appeal row to the appeals table."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO appeals (appeal_id, content_id, creator_id, appeal_reasoning, context, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["appeal_id"],
            entry["content_id"],
            entry.get("creator_id", ""),
            entry["appeal_reasoning"],
            entry.get("context", ""),
            entry["status"],
            entry["timestamp"],
        ))


def get_appeals_log() -> List[dict]:
    """Return all appeal entries with original classification data, newest first."""
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT
                a.appeal_id, a.content_id, a.creator_id,
                a.appeal_reasoning, a.context, a.status, a.timestamp,
                s.attribution, s.confidence, s.llm_score,
                s.stylometric_score, s.label_text
            FROM appeals a
            LEFT JOIN submissions s ON a.content_id = s.content_id
            ORDER BY a.id DESC
        """).fetchall()
    return [dict(row) for row in rows]


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)
