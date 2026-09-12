"""SQLite persistence: users, every message sent, every tap, every mood signal.

One file (josiyam.db), no server. Tone weights are no longer stored — they are
derived from the feedback table, so the learning is inspectable and per-user.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "josiyam.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    name       TEXT,
    tz         TEXT DEFAULT 'Asia/Kolkata',
    persona    TEXT,                     -- unused, kept for old rows
    sunsign    TEXT,
    ics_url    TEXT,
    step       TEXT DEFAULT 'name',      -- onboarding: name → tz → sunsign → ics → done
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       INTEGER,
    tg_message_id INTEGER,
    event_uid     TEXT,
    event_title   TEXT,
    event_class   TEXT,                  -- hard / neutral / nourishing
    kind          TEXT,                  -- pre / post / day
    register      TEXT,                  -- warm / punchy / cosmic
    text          TEXT,
    sent_at       TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    chat_id    INTEGER,
    verdict    TEXT,                     -- up / down
    latency_s  REAL,                     -- seconds from send to tap: a passive engagement signal
    tapped_at  TEXT
);
CREATE TABLE IF NOT EXISTS mood (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER,
    message_id  INTEGER,
    event_uid   TEXT,
    event_title TEXT,
    source      TEXT,                    -- tap / passive
    value       TEXT,                    -- rough / fine / great  (tap)  |  e.g. dense_day (passive)
    at          TEXT
);
CREATE TABLE IF NOT EXISTS journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER,
    text        TEXT,
    event_uid   TEXT,                    -- the meeting the bot last spoke about, if recent
    event_title TEXT,
    at          TEXT
);
CREATE TABLE IF NOT EXISTS sent (
    chat_id INTEGER,
    key     TEXT,
    PRIMARY KEY (chat_id, key)
);
"""

SEED = {"josiyam": 1.0, "hype": 1.0, "warm": 1.0, "quote": 1.0}

SUNSIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        cols = {r[1] for r in _conn.execute("PRAGMA table_info(users)")}
        if "sunsign" not in cols:
            _conn.execute("ALTER TABLE users ADD COLUMN sunsign TEXT")
        _migrate_state_json()
    return _conn


def _migrate_state_json() -> None:
    """One-off: pull chat_id / ics_url from the old state.json so a running user isn't dropped."""
    p = Path("state.json")
    if not p.exists():
        return
    try:
        s = json.loads(p.read_text())
    except Exception:
        return
    if s.get("chat_id") and not get_user(s["chat_id"]):
        _conn.execute(
            "INSERT INTO users (chat_id, name, ics_url, step, created_at) VALUES (?,?,?,?,?)",
            (s["chat_id"], None, s.get("ics_url"), "done" if s.get("ics_url") else "name", _now()),
        )
        for k in s.get("sent", []):
            _conn.execute("INSERT OR IGNORE INTO sent VALUES (?,?)", (s["chat_id"], k))
        _conn.commit()
    p.rename("state.json.migrated")


# ---------------------------------------------------------------- users ----
def get_user(chat_id: int) -> sqlite3.Row | None:
    return db().execute("SELECT * FROM users WHERE chat_id=?", (chat_id,)).fetchone()


def ensure_user(chat_id: int) -> sqlite3.Row:
    u = get_user(chat_id)
    if u is None:
        db().execute("INSERT INTO users (chat_id, created_at) VALUES (?,?)", (chat_id, _now()))
        db().commit()
        u = get_user(chat_id)
    return u


def set_user(chat_id: int, **fields) -> None:
    cols = ", ".join(f"{k}=?" for k in fields)
    db().execute(f"UPDATE users SET {cols} WHERE chat_id=?", (*fields.values(), chat_id))
    db().commit()


def connected_users() -> list[sqlite3.Row]:
    return db().execute("SELECT * FROM users WHERE ics_url IS NOT NULL").fetchall()


def delete_user(chat_id: int) -> None:
    db().execute("DELETE FROM users WHERE chat_id=?", (chat_id,))
    db().execute("DELETE FROM sent WHERE chat_id=?", (chat_id,))
    db().commit()


# ------------------------------------------------------------- messages ----
def record_message(chat_id: int, kind: str, register: str, text: str, ev: dict | None) -> int:
    cur = db().execute(
        "INSERT INTO messages (chat_id, event_uid, event_title, event_class, kind, register, text, sent_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (chat_id, (ev or {}).get("uid"), (ev or {}).get("title"), (ev or {}).get("klass"), kind, register, text, _now()),
    )
    db().commit()
    return cur.lastrowid


def set_tg_message_id(message_id: int, tg_message_id: int) -> None:
    db().execute("UPDATE messages SET tg_message_id=? WHERE id=?", (tg_message_id, message_id))
    db().commit()


def last_register(chat_id: int) -> str | None:
    r = db().execute("SELECT register FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1", (chat_id,)).fetchone()
    return r["register"] if r else None


def get_message(message_id: int) -> sqlite3.Row | None:
    return db().execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()


# ------------------------------------------------------------- feedback ----
def record_feedback(message_id: int, chat_id: int, verdict: str) -> float:
    m = get_message(message_id)
    latency = None
    if m and m["sent_at"]:
        latency = (datetime.now(timezone.utc) - datetime.fromisoformat(m["sent_at"])).total_seconds()
    db().execute(
        "INSERT INTO feedback (message_id, chat_id, verdict, latency_s, tapped_at) VALUES (?,?,?,?,?)",
        (message_id, chat_id, verdict, latency, _now()),
    )
    db().commit()
    return latency or 0.0


def record_mood(chat_id: int, value: str, source: str = "tap", message_id: int | None = None, ev: dict | None = None) -> None:
    m = get_message(message_id) if message_id else None
    db().execute(
        "INSERT INTO mood (chat_id, message_id, event_uid, event_title, source, value, at) VALUES (?,?,?,?,?,?,?)",
        (chat_id, message_id, (ev or {}).get("uid") or (m["event_uid"] if m else None),
         (ev or {}).get("title") or (m["event_title"] if m else None), source, value, _now()),
    )
    db().commit()


def recent_moods(chat_id: int, hours: int = 36) -> list[sqlite3.Row]:
    return db().execute(
        "SELECT * FROM mood WHERE chat_id=? AND source='tap' AND at >= datetime('now', ?) ORDER BY at DESC",
        (chat_id, f"-{hours} hours"),
    ).fetchall()


def moods_by_event(chat_id: int, since_iso: str) -> dict[str, str]:
    rows = db().execute(
        "SELECT event_uid, value FROM mood WHERE chat_id=? AND source='tap' AND at >= ? ORDER BY id", (chat_id, since_iso)
    ).fetchall()
    return {r["event_uid"]: r["value"] for r in rows if r["event_uid"]}


def journal_since(chat_id: int, since_iso: str) -> list[sqlite3.Row]:
    return db().execute("SELECT * FROM journal WHERE chat_id=? AND at >= ? ORDER BY id", (chat_id, since_iso)).fetchall()


def tone_weights(chat_id: int) -> dict[str, float]:
    """All voices start equal; recency-weighted feedback moves them. Nothing is ever banned."""
    w = dict(SEED)
    rows = db().execute(
        "SELECT f.verdict, m.register FROM feedback f JOIN messages m ON m.id=f.message_id "
        "WHERE f.chat_id=? ORDER BY f.tapped_at DESC LIMIT 30",
        (chat_id,),
    ).fetchall()
    for i, r in enumerate(rows):
        if r["register"] not in w:
            continue
        delta = (0.5 if r["verdict"] == "up" else -0.4) * (0.92 ** i)
        w[r["register"]] = max(0.1, w[r["register"]] + delta)
    return w


def stats(chat_id: int) -> dict:
    d = db()
    total = d.execute("SELECT COUNT(*) FROM messages WHERE chat_id=?", (chat_id,)).fetchone()[0]
    fb = d.execute("SELECT verdict, COUNT(*) c FROM feedback WHERE chat_id=? GROUP BY verdict", (chat_id,)).fetchall()
    fb = {r["verdict"]: r["c"] for r in fb}
    per_reg = d.execute(
        "SELECT m.register, SUM(f.verdict='up') up, COUNT(*) n FROM feedback f JOIN messages m ON m.id=f.message_id "
        "WHERE f.chat_id=? GROUP BY m.register", (chat_id,)
    ).fetchall()
    lat = d.execute("SELECT AVG(latency_s) FROM feedback WHERE chat_id=?", (chat_id,)).fetchone()[0]
    moods = d.execute("SELECT value, COUNT(*) c FROM mood WHERE chat_id=? AND source='tap' GROUP BY value", (chat_id,)).fetchall()
    journal = d.execute("SELECT COUNT(*) FROM journal WHERE chat_id=?", (chat_id,)).fetchone()[0]
    return {
        "messages": total,
        "up": fb.get("up", 0),
        "down": fb.get("down", 0),
        "per_register": {r["register"]: (r["up"], r["n"]) for r in per_reg},
        "avg_latency_s": lat,
        "moods": {r["value"]: r["c"] for r in moods},
        "journal": journal,
        "weights": tone_weights(chat_id),
    }


# -------------------------------------------------------------- journal ----
def last_message_within(chat_id: int, minutes: int = 90) -> sqlite3.Row | None:
    return db().execute(
        "SELECT * FROM messages WHERE chat_id=? AND kind IN ('pre','post') AND sent_at >= datetime('now', ?) "
        "ORDER BY id DESC LIMIT 1", (chat_id, f"-{minutes} minutes")
    ).fetchone()


def record_journal(chat_id: int, text: str) -> tuple[int, str | None]:
    m = last_message_within(chat_id)
    title = m["event_title"] if m else None
    cur = db().execute(
        "INSERT INTO journal (chat_id, text, event_uid, event_title, at) VALUES (?,?,?,?,?)",
        (chat_id, text, m["event_uid"] if m else None, title, _now()),
    )
    db().commit()
    return cur.lastrowid, title


def recent_journal(chat_id: int, hours: int = 48, limit: int = 5) -> list[sqlite3.Row]:
    return db().execute(
        "SELECT * FROM journal WHERE chat_id=? AND at >= datetime('now', ?) ORDER BY id DESC LIMIT ?",
        (chat_id, f"-{hours} hours", limit),
    ).fetchall()


def journal_days(chat_id: int, days: int = 7) -> list[sqlite3.Row]:
    return db().execute(
        "SELECT * FROM journal WHERE chat_id=? AND at >= datetime('now', ?) ORDER BY id ASC",
        (chat_id, f"-{days} days"),
    ).fetchall()


# ----------------------------------------------------------------- sent ----
def already_sent(chat_id: int, key: str) -> bool:
    return db().execute("SELECT 1 FROM sent WHERE chat_id=? AND key=?", (chat_id, key)).fetchone() is not None


def mark_sent(chat_id: int, key: str) -> None:
    db().execute("INSERT OR IGNORE INTO sent VALUES (?,?)", (chat_id, key))
    db().commit()


def clear_sent(chat_id: int) -> None:
    db().execute("DELETE FROM sent WHERE chat_id=?", (chat_id,))
    db().commit()
