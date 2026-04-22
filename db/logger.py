import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dlp_logs.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    schema = SCHEMA_PATH.read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()


def insert_submission(
    risk_tier: str,
    matched_patterns: list,
    redacted_preview: str,
    original_length: int,
    encoding_detected: str | None,
) -> int:
    conn = _connect()
    ts = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO submissions
            (timestamp, risk_tier, matched_patterns, redacted_preview,
             original_length, encoding_detected, passed_to_llm)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (ts, risk_tier, json.dumps(matched_patterns), redacted_preview[:500],
         original_length, encoding_detected),
    )
    submission_id = cur.lastrowid

    for match in matched_patterns:
        conn.execute(
            """
            INSERT INTO pattern_hits (submission_id, category, pattern_name, tier)
            VALUES (?, ?, ?, ?)
            """,
            (submission_id, match["category"], match["name"], match["tier"]),
        )

    conn.commit()
    conn.close()
    return submission_id


def mark_passed_to_llm(submission_id: int, llm_response_id: str | None):
    conn = _connect()
    conn.execute(
        "UPDATE submissions SET passed_to_llm=1, llm_response_id=? WHERE id=?",
        (llm_response_id, submission_id),
    )
    conn.commit()
    conn.close()


def mark_blocked(submission_id: int, reason: str):
    conn = _connect()
    conn.execute(
        "UPDATE submissions SET reason_blocked=? WHERE id=?",
        (reason, submission_id),
    )
    conn.commit()
    conn.close()


def query_submissions(window_days: int | None = None) -> list[dict]:
    conn = _connect()
    if window_days:
        cur = conn.execute(
            """
            SELECT * FROM submissions
            WHERE timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
            """,
            (f"-{window_days} days",),
        )
    else:
        cur = conn.execute("SELECT * FROM submissions ORDER BY timestamp DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def query_pattern_hits(window_days: int | None = None) -> list[dict]:
    conn = _connect()
    if window_days:
        cur = conn.execute(
            """
            SELECT ph.* FROM pattern_hits ph
            JOIN submissions s ON ph.submission_id = s.id
            WHERE s.timestamp >= datetime('now', ?)
            """,
            (f"-{window_days} days",),
        )
    else:
        cur = conn.execute("SELECT * FROM pattern_hits")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def clear_all_logs():
    conn = _connect()
    conn.execute("DELETE FROM pattern_hits")
    conn.execute("DELETE FROM submissions")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('submissions','pattern_hits')")
    conn.commit()
    conn.close()
