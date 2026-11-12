"""Import and filter contacts from profiles.csv."""

from __future__ import annotations

import csv
from pathlib import Path

from app.config import DEFAULT_CSV, settings
from app.database import fetchall, fetchone, get_db
from app.filters import (
    age_from_birthday,
    is_valid_email,
    normalize_email,
    profile_passes_filters,
    slug_to_name,
)
from app.scraper import scrape_names_batch


async def import_csv(
    csv_path: Path | None = None,
    campaign_id: int = 1,
    scrape_names: bool = True,
    min_age: int | None = None,
    max_age: int | None = None,
) -> dict:
    path = csv_path or DEFAULT_CSV
    min_age = min_age if min_age is not None else settings.min_age
    max_age = max_age if max_age is not None else settings.max_age

    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    candidates = []
    skipped_no_email = 0
    skipped_age = 0
    seen_emails: set[str] = set()

    for row in rows:
        email = normalize_email(row.get("email"))
        if not is_valid_email(email):
            skipped_no_email += 1
            continue
        if email.lower() in seen_emails:
            continue
        if not profile_passes_filters(row, min_age, max_age):
            skipped_age += 1
            continue
        seen_emails.add(email.lower())
        profile_url = (row.get("profile_url") or "").strip()
        candidates.append(
            {
                "profile_url": profile_url,
                "email": email,
                "name": slug_to_name(profile_url) if profile_url else "Friend",
                "birthday": (row.get("birthday") or "").strip(),
                "age": age_from_birthday(row.get("birthday")),
                "telegram": (row.get("telegram") or "").strip(),
                "whatsapp": (row.get("whatsapp") or "").strip(),
            }
        )

    names_map: dict[str, str] = {}
    if scrape_names:
        urls = [c["profile_url"] for c in candidates if c["profile_url"]]
        names_map = await scrape_names_batch(urls, concurrency=5)

    inserted = 0
    duplicates = 0

    async with get_db() as db:
        for contact in candidates:
            url = contact["profile_url"]
            if url in names_map:
                contact["name"] = names_map[url]

            existing = await fetchone(
                db, "SELECT id FROM contacts WHERE email = ?", (contact["email"],)
            )
            if existing:
                duplicates += 1
                continue

            await db.execute(
                """
                INSERT INTO contacts (
                    profile_url, email, name, birthday, age,
                    telegram, whatsapp, campaign_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
                """,
                (
                    contact["profile_url"],
                    contact["email"],
                    contact["name"],
                    contact["birthday"],
                    contact["age"],
                    contact["telegram"],
                    contact["whatsapp"],
                    campaign_id,
                ),
            )
            inserted += 1
        await db.commit()

        total = await fetchone(db, "SELECT COUNT(*) AS c FROM contacts")
        pending = await fetchone(
            db, "SELECT COUNT(*) AS c FROM contacts WHERE status = 'Pending'"
        )

    return {
        "csv_rows": len(rows),
        "candidates": len(candidates),
        "inserted": inserted,
        "duplicates": duplicates,
        "skipped_no_email": skipped_no_email,
        "skipped_age": skipped_age,
        "names_scraped": len(names_map),
        "total_contacts": total["c"] if total else 0,
        "pending_contacts": pending["c"] if pending else 0,
        "min_age": min_age,
        "max_age": max_age,
    }


async def resolve_missing_names(concurrency: int = 5) -> int:
    async with get_db() as db:
        rows = await fetchall(
            db,
            """
            SELECT id, profile_url FROM contacts
            WHERE profile_url IS NOT NULL AND profile_url != ''
              AND (name IS NULL OR name = '' OR name = 'Friend')
            """,
        )

    if not rows:
        return 0

    urls = [row["profile_url"] for row in rows]
    names_map = await scrape_names_batch(urls, concurrency=concurrency)

    updated = 0
    async with get_db() as db:
        for row in rows:
            name = names_map.get(row["profile_url"])
            if not name:
                continue
            await db.execute(
                "UPDATE contacts SET name = ? WHERE id = ?",
                (name, row["id"]),
            )
            updated += 1
        await db.commit()
    return updated
