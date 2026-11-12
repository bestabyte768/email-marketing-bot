"""Scrape profile names from chatkk.com profile pages."""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.filters import slug_to_name

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def extract_name_from_html(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
        if name and len(name) < 80:
            return name

    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        match = re.match(r"^Name\s*(.+)$", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    title = soup.find("title")
    if title:
        match = re.search(
            r"profile of\s+(.+?)\s+from",
            title.get_text(strip=True),
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip().title()

    return None


async def fetch_profile_name(
    profile_url: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    if not profile_url:
        return "Friend"

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True)

    try:
        response = await client.get(profile_url)
        response.raise_for_status()
        name = extract_name_from_html(response.text)
        return name or slug_to_name(profile_url)
    except Exception:
        return slug_to_name(profile_url)
    finally:
        if own_client:
            await client.aclose()


async def scrape_names_batch(
    urls: list[str],
    concurrency: int = 5,
    on_progress=None,
) -> dict[str, str]:
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, str] = {}

    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=True) as client:

        async def worker(url: str) -> None:
            async with semaphore:
                results[url] = await fetch_profile_name(url, client)
                if on_progress:
                    await on_progress(url, results[url])

        await asyncio.gather(*(worker(url) for url in urls))

    return results
