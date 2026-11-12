"""Background campaign worker with random delays."""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime
from typing import Optional

from app.config import settings
from app.database import fetchone, get_db
from app.mailer import render_template, send_email

# Shared runtime state for the dashboard
worker_state = {
    "running": False,
    "paused": False,
    "stop_requested": False,
    "current_email": None,
    "last_status": "Idle",
    "next_send_at": None,
    "waiting_seconds": 0,
}


class CampaignWorker:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> str:
        if self.is_running:
            if worker_state["paused"]:
                worker_state["paused"] = False
                worker_state["last_status"] = "Resumed"
                return "Campaign resumed"
            return "Campaign already running"
        worker_state.update(
            {
                "running": True,
                "paused": False,
                "stop_requested": False,
                "last_status": "Starting",
                "next_send_at": None,
                "waiting_seconds": 0,
            }
        )
        async with get_db() as db:
            await db.execute(
                "UPDATE campaigns SET status = 'running' WHERE id = 1"
            )
            await db.commit()
        self._task = asyncio.create_task(self._run_loop())
        return "Campaign started"

    async def pause(self) -> str:
        if not self.is_running:
            return "No active campaign"
        worker_state["paused"] = True
        worker_state["last_status"] = "Paused"
        async with get_db() as db:
            await db.execute(
                "UPDATE campaigns SET status = 'paused' WHERE id = 1"
            )
            await db.commit()
        return "Campaign paused"

    async def stop(self) -> str:
        worker_state["stop_requested"] = True
        worker_state["paused"] = False
        worker_state["last_status"] = "Stopping"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        worker_state["running"] = False
        worker_state["current_email"] = None
        worker_state["next_send_at"] = None
        worker_state["waiting_seconds"] = 0
        worker_state["last_status"] = "Stopped"
        async with get_db() as db:
            await db.execute(
                "UPDATE campaigns SET status = 'stopped' WHERE id = 1"
            )
            await db.commit()
        return "Campaign stopped"

    async def send_one_now(self) -> str:
        """Send the next queued contact immediately (no delay)."""
        if self.is_running and not worker_state["paused"]:
            return "Stop or Pause the campaign first, then use Send."

        if not await self._reset_daily_counter_if_needed():
            return "Daily limit reached — try again tomorrow."

        contact = await self._next_contact()
        if not contact:
            return "Queue empty — nothing to send."

        await self._process_contact(contact, allow_retry_wait=False)
        return worker_state["last_status"] or "Send finished"

    async def _run_loop(self) -> None:
        try:
            while not worker_state["stop_requested"]:
                while worker_state["paused"] and not worker_state["stop_requested"]:
                    worker_state["last_status"] = "Paused"
                    await asyncio.sleep(1)

                if worker_state["stop_requested"]:
                    break

                if not await self._reset_daily_counter_if_needed():
                    worker_state["last_status"] = "Daily limit reached — paused until tomorrow"
                    worker_state["paused"] = True
                    async with get_db() as db:
                        await db.execute(
                            "UPDATE campaigns SET status = 'paused' WHERE id = 1"
                        )
                        await db.commit()
                    await asyncio.sleep(30)
                    continue

                contact = await self._next_contact()
                if not contact:
                    worker_state["last_status"] = "Queue empty — campaign complete"
                    worker_state["running"] = False
                    async with get_db() as db:
                        await db.execute(
                            "UPDATE campaigns SET status = 'idle' WHERE id = 1"
                        )
                        await db.commit()
                    break

                await self._process_contact(contact, allow_retry_wait=True)

                if worker_state["stop_requested"]:
                    break

                delay = random.randint(
                    settings.delay_min_minutes * 60,
                    settings.delay_max_minutes * 60,
                )
                worker_state["waiting_seconds"] = delay
                worker_state["next_send_at"] = datetime.now().isoformat(timespec="seconds")
                worker_state["last_status"] = f"Waiting {delay // 60}m {delay % 60}s"
                await self._interruptible_sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            worker_state["last_status"] = f"Worker error: {exc}"
            worker_state["running"] = False
            async with get_db() as db:
                await db.execute(
                    "UPDATE campaigns SET status = 'stopped' WHERE id = 1"
                )
                await db.commit()
        finally:
            worker_state["running"] = False
            worker_state["current_email"] = None
            worker_state["next_send_at"] = None
            worker_state["waiting_seconds"] = 0
            self._task = None

    async def _interruptible_sleep(self, seconds: int) -> None:
        for remaining in range(seconds, 0, -1):
            if worker_state["stop_requested"]:
                return
            while worker_state["paused"] and not worker_state["stop_requested"]:
                worker_state["last_status"] = "Paused"
                await asyncio.sleep(1)
            if worker_state["stop_requested"]:
                return
            worker_state["waiting_seconds"] = remaining
            worker_state["last_status"] = f"Waiting {remaining // 60}m {remaining % 60}s"
            await asyncio.sleep(1)

    async def _reset_daily_counter_if_needed(self) -> bool:
        today = date.today().isoformat()
        async with get_db() as db:
            campaign = await fetchone(db, "SELECT * FROM campaigns WHERE id = 1")
            if not campaign:
                return False
            sent_today = campaign["emails_sent_today"]
            last_date = campaign["last_sent_date"]
            daily_limit = campaign["daily_limit"] or settings.daily_limit

            if last_date != today:
                await db.execute(
                    "UPDATE campaigns SET emails_sent_today = 0, last_sent_date = ? WHERE id = 1",
                    (today,),
                )
                await db.commit()
                return True

            return sent_today < daily_limit

    async def _next_contact(self):
        async with get_db() as db:
            # Prefer retry contacts, then pending
            contact = await fetchone(
                db,
                """
                SELECT * FROM contacts
                WHERE status IN ('Retry', 'Pending')
                ORDER BY
                    CASE status WHEN 'Retry' THEN 0 ELSE 1 END,
                    id ASC
                LIMIT 1
                """,
            )
            return dict(contact) if contact else None

    async def _process_contact(self, contact: dict, allow_retry_wait: bool = True) -> None:
        contact_id = contact["id"]
        email = contact["email"]
        name = contact.get("name") or "Friend"
        worker_state["current_email"] = email
        worker_state["last_status"] = f"Sending to {email}"

        async with get_db() as db:
            await db.execute(
                "UPDATE contacts SET status = 'Sending' WHERE id = ?",
                (contact_id,),
            )
            template = await fetchone(db, "SELECT * FROM email_template WHERE id = 1")
            await db.commit()

        variables = {
            "name": name,
            "email": email,
            "birthday": contact.get("birthday") or "",
            "age": str(contact.get("age") or ""),
            "profile_url": contact.get("profile_url") or "",
        }
        subject = render_template(template["subject"], variables)
        body = render_template(template["body"], variables)

        try:
            await asyncio.to_thread(send_email, email, subject, body)
            now = datetime.now().isoformat(timespec="seconds")
            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE contacts
                    SET status = 'Sent', sent_at = ?, error_message = NULL
                    WHERE id = ?
                    """,
                    (now, contact_id),
                )
                await db.execute(
                    """
                    UPDATE campaigns
                    SET emails_sent_today = emails_sent_today + 1,
                        last_sent_date = ?
                    WHERE id = 1
                    """,
                    (date.today().isoformat(),),
                )
                await db.execute(
                    """
                    INSERT INTO send_logs (contact_id, email, name, status, message)
                    VALUES (?, ?, ?, 'Sent', ?)
                    """,
                    (contact_id, email, name, "Email sent successfully"),
                )
                await db.commit()
            worker_state["last_status"] = f"Sent to {email}"
        except Exception as exc:
            retry_count = contact.get("retry_count") or 0
            if retry_count < 1:
                new_status = "Retry"
                retry_count += 1
                extra = random.randint(15 * 60, 30 * 60) if allow_retry_wait else 0
            else:
                new_status = "Failed"
                extra = 0

            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE contacts
                    SET status = ?, retry_count = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (new_status, retry_count, str(exc), contact_id),
                )
                await db.execute(
                    """
                    INSERT INTO send_logs (contact_id, email, name, status, message)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (contact_id, email, name, new_status, str(exc)),
                )
                await db.commit()

            worker_state["last_status"] = f"{new_status}: {email} — {exc}"
            if extra and allow_retry_wait:
                worker_state["last_status"] = (
                    f"Retry scheduled for {email}; waiting {extra // 60}m"
                )
                await self._interruptible_sleep(extra)
        finally:
            worker_state["current_email"] = None


campaign_worker = CampaignWorker()
