"""SQLite database helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager

import aiosqlite

from app.config import DB_PATH, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_template (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    subject TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    daily_limit INTEGER NOT NULL DEFAULT 50,
    emails_sent_today INTEGER NOT NULL DEFAULT 0,
    last_sent_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_url TEXT,
    email TEXT NOT NULL,
    name TEXT,
    birthday TEXT,
    age INTEGER,
    telegram TEXT,
    whatsapp TEXT,
    campaign_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Pending',
    sent_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(email)
);

CREATE TABLE IF NOT EXISTS send_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    email TEXT,
    name TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_campaign ON contacts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_send_logs_created ON send_logs(created_at);
"""


DEFAULT_TEMPLATE = {
    "subject": "Hello {{name}}",
    "body": """Hi {{name}},

I came across your profile and wanted to reach out.

Best regards""",
}


async def fetchone(db: aiosqlite.Connection, sql: str, params: tuple = ()):
    async with db.execute(sql, params) as cursor:
        return await cursor.fetchone()


async def fetchall(db: aiosqlite.Connection, sql: str, params: tuple = ()):
    async with db.execute(sql, params) as cursor:
        return await cursor.fetchall()


@asynccontextmanager
async def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with get_db() as db:
        await db.executescript(SCHEMA)
        row = await fetchone(db, "SELECT id FROM email_template WHERE id = 1")
        if not row:
            await db.execute(
                "INSERT INTO email_template (id, subject, body) VALUES (1, ?, ?)",
                (DEFAULT_TEMPLATE["subject"], DEFAULT_TEMPLATE["body"]),
            )
        row = await fetchone(db, "SELECT id FROM campaigns LIMIT 1")
        if not row:
            await db.execute(
                "INSERT INTO campaigns (name, status, daily_limit) VALUES (?, 'idle', ?)",
                ("Default Campaign", settings.daily_limit),
            )
        await db.commit()


async def get_setting(db: aiosqlite.Connection, key: str, default: str = "") -> str:
    row = await fetchone(db, "SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
