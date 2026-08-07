"""
database.py
Quản lý toàn bộ dữ liệu của bot bằng SQLite:
- study_sessions: các buổi học đã log (môn + chủ đề + ngày bắt đầu)
- review_items: các mốc ôn tập sinh ra theo spaced repetition (1-3-7-14-30 ngày)
- assignments: bài tập / deadline cần nhắc
- settings: lưu chat_id và giờ nhắc mỗi ngày của user
"""

import os
import sqlite3
from datetime import date, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "srbot.db")

# Khoảng cách ôn tập tính bằng số ngày sau ngày bắt đầu học
REVIEW_INTERVALS = [1, 3, 7, 14, 30]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                start_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                due_date TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                done_date TEXT,
                FOREIGN KEY (session_id) REFERENCES study_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                subject TEXT,
                deadline_date TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER PRIMARY KEY,
                reminder_hour INTEGER NOT NULL DEFAULT 7,
                reminder_minute INTEGER NOT NULL DEFAULT 0
            );
            """
        )


# ---------- Study sessions & reviews ----------

def add_study_session(chat_id: int, subject: str, topic: str, start_date: date):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO study_sessions (chat_id, subject, topic, start_date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, subject, topic, start_date.isoformat(), date.today().isoformat()),
        )
        session_id = cur.lastrowid
        for i, offset in enumerate(REVIEW_INTERVALS, start=1):
            due = start_date + timedelta(days=offset)
            conn.execute(
                "INSERT INTO review_items (session_id, chat_id, round_number, due_date) "
                "VALUES (?, ?, ?, ?)",
                (session_id, chat_id, i, due.isoformat()),
            )
        return session_id


def get_due_reviews(chat_id: int, up_to: date):
    """Lấy các review chưa done, due_date <= up_to (bao gồm quá hạn)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.round_number, r.due_date, s.subject, s.topic, s.start_date
            FROM review_items r
            JOIN study_sessions s ON s.id = r.session_id
            WHERE r.chat_id = ? AND r.done = 0 AND r.due_date <= ?
            ORDER BY r.due_date ASC
            """,
            (chat_id, up_to.isoformat()),
        ).fetchall()
        return rows


def mark_review_done(review_id: int, chat_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE review_items SET done = 1, done_date = ? "
            "WHERE id = ? AND chat_id = ? AND done = 0",
            (date.today().isoformat(), review_id, chat_id),
        )
        return cur.rowcount > 0


# ---------- Assignments ----------

def add_assignment(chat_id: int, name: str, deadline: date, subject: str | None = None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO assignments (chat_id, name, subject, deadline_date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, name, subject, deadline.isoformat(), date.today().isoformat()),
        )
        return cur.lastrowid


def get_due_assignments(chat_id: int, up_to: date):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, subject, deadline_date
            FROM assignments
            WHERE chat_id = ? AND done = 0 AND deadline_date <= ?
            ORDER BY deadline_date ASC
            """,
            (chat_id, up_to.isoformat()),
        ).fetchall()
        return rows


def mark_assignment_done(assignment_id: int, chat_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE assignments SET done = 1 WHERE id = ? AND chat_id = ? AND done = 0",
            (assignment_id, chat_id),
        )
        return cur.rowcount > 0


# ---------- Danh sách tổng hợp / xoá ----------

def list_all_pending(chat_id: int):
    with get_conn() as conn:
        reviews = conn.execute(
            """
            SELECT r.id, r.round_number, r.due_date, s.subject, s.topic
            FROM review_items r JOIN study_sessions s ON s.id = r.session_id
            WHERE r.chat_id = ? AND r.done = 0
            ORDER BY r.due_date ASC
            """,
            (chat_id,),
        ).fetchall()
        assignments = conn.execute(
            "SELECT id, name, subject, deadline_date FROM assignments "
            "WHERE chat_id = ? AND done = 0 ORDER BY deadline_date ASC",
            (chat_id,),
        ).fetchall()
        return reviews, assignments


def delete_review(review_id: int, chat_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM review_items WHERE id = ? AND chat_id = ?", (review_id, chat_id)
        )
        return cur.rowcount > 0


def delete_assignment(assignment_id: int, chat_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM assignments WHERE id = ? AND chat_id = ?", (assignment_id, chat_id)
        )
        return cur.rowcount > 0


# ---------- Settings (giờ nhắc + chat_id) ----------

def upsert_settings(chat_id: int, hour: int | None = None, minute: int | None = None):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO settings (chat_id, reminder_hour, reminder_minute) VALUES (?, ?, ?)",
                (chat_id, hour if hour is not None else 7, minute if minute is not None else 0),
            )
        else:
            new_hour = hour if hour is not None else existing["reminder_hour"]
            new_minute = minute if minute is not None else existing["reminder_minute"]
            conn.execute(
                "UPDATE settings SET reminder_hour = ?, reminder_minute = ? WHERE chat_id = ?",
                (new_hour, new_minute, chat_id),
            )


def get_all_settings():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM settings").fetchall()


def get_settings(chat_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
