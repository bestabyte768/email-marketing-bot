"""Dashboard stats and data helpers."""

from __future__ import annotations

from datetime import date

from app.config import refresh_settings
from app.database import fetchall, fetchone, get_db
from app.worker import worker_state


async def get_dashboard_stats() -> dict:
    settings = refresh_settings()
    today = date.today().isoformat()
    async with get_db() as db:
        campaign = await fetchone(db, "SELECT * FROM campaigns WHERE id = 1")
        template = await fetchone(db, "SELECT * FROM email_template WHERE id = 1")

        if campaign and campaign["last_sent_date"] != today:
            sent_today = 0
        else:
            sent_today = campaign["emails_sent_today"] if campaign else 0

        daily_limit = (
            campaign["daily_limit"] if campaign else settings.daily_limit
        ) or settings.daily_limit

        counts = await fetchone(
            db,
            """
            SELECT
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'Retry' THEN 1 ELSE 0 END) AS retry,
                SUM(CASE WHEN status = 'Sending' THEN 1 ELSE 0 END) AS sending,
                SUM(CASE WHEN status = 'Sent' THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'Skipped' THEN 1 ELSE 0 END) AS skipped,
                COUNT(*) AS total
            FROM contacts
            """,
        )
        sent = counts["sent"] or 0
        failed = counts["failed"] or 0
        attempted = sent + failed
        success_rate = round((sent / attempted) * 100, 1) if attempted else 0.0

        recent_logs = await fetchall(
            db,
            """
            SELECT * FROM send_logs
            ORDER BY id DESC
            LIMIT 30
            """,
        )
        contacts = await fetchall(
            db,
            """
            SELECT id, name, email, age, status, sent_at, retry_count, error_message
            FROM contacts
            ORDER BY
                CASE status
                    WHEN 'Sending' THEN 0
                    WHEN 'Retry' THEN 1
                    WHEN 'Pending' THEN 2
                    WHEN 'Failed' THEN 3
                    ELSE 4
                END,
                id ASC
            LIMIT 100
            """,
        )

    remaining = max(daily_limit - sent_today, 0)
    queue_size = (counts["pending"] or 0) + (counts["retry"] or 0)

    return {
        "campaign": dict(campaign) if campaign else {},
        "template": dict(template) if template else {},
        "sent_today": sent_today,
        "daily_limit": daily_limit,
        "remaining_today": remaining,
        "queue_size": queue_size,
        "success_rate": success_rate,
        "counts": {
            "pending": counts["pending"] or 0,
            "retry": counts["retry"] or 0,
            "sending": counts["sending"] or 0,
            "sent": counts["sent"] or 0,
            "failed": counts["failed"] or 0,
            "skipped": counts["skipped"] or 0,
            "total": counts["total"] or 0,
        },
        "worker": dict(worker_state),
        "recent_logs": [dict(r) for r in recent_logs],
        "contacts": [dict(c) for c in contacts],
        "settings": {
            "smtp_host": settings.smtp_host,
            "smtp_user": settings.smtp_user,
            "smtp_configured": bool(settings.smtp_user and settings.smtp_password),
            "min_age": settings.min_age,
            "max_age": settings.max_age,
            "delay_min": settings.delay_min_minutes,
            "delay_max": settings.delay_max_minutes,
        },
    }
