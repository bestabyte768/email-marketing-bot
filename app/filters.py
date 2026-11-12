"""Profile filtering and validation utilities."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from app.config import settings

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
INVALID_EMAIL_VALUES = {"", "sharedprivately", "shared privately", "n/a", "none"}


def normalize_email(value: str | None) -> str:
    return (value or "").strip()


def is_valid_email(value: str | None) -> bool:
    email = normalize_email(value)
    if email.lower() in INVALID_EMAIL_VALUES:
        return False
    return bool(EMAIL_RE.match(email))


def parse_birthday(value: str | None) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    if text.lower() in INVALID_EMAIL_VALUES or "shared" in text.lower():
        return None
    formats = ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d/%m/%Y")
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def calculate_age(birthday: date, on_date: date | None = None) -> int:
    today = on_date or date.today()
    years = today.year - birthday.year
    if (today.month, today.day) < (birthday.month, birthday.day):
        years -= 1
    return years


def age_from_birthday(value: str | None, on_date: date | None = None) -> Optional[int]:
    birthday = parse_birthday(value)
    if not birthday:
        return None
    return calculate_age(birthday, on_date)


def passes_age_filter(
    birthday: str | None,
    min_age: int | None = None,
    max_age: int | None = None,
    on_date: date | None = None,
) -> bool:
    age = age_from_birthday(birthday, on_date)
    if age is None:
        return False
    lo = min_age if min_age is not None else settings.min_age
    hi = max_age if max_age is not None else settings.max_age
    return lo <= age <= hi


def profile_passes_filters(row: dict, min_age: int | None = None, max_age: int | None = None) -> bool:
    if not is_valid_email(row.get("email")):
        return False
    return passes_age_filter(row.get("birthday"), min_age, max_age)


def slug_to_name(profile_url: str) -> str:
    """Fallback name from profile URL slug."""
    slug = profile_url.rstrip("/").split("/")[-1]
    slug = re.sub(r"\d+$", "", slug)
    return slug.replace("-", " ").strip().title() or "Friend"
