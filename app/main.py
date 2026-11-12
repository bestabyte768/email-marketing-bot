"""FastAPI email bot dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_db, init_db
from app.importer import import_csv, resolve_missing_names
from app.stats import get_dashboard_stats
from app.worker import campaign_worker

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield
    if campaign_worker.is_running:
        await campaign_worker.stop()


app = FastAPI(title="Email Bot", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"stats": stats, "flash": None},
    )


@app.get("/partials/stats", response_class=HTMLResponse)
async def partial_stats(request: Request):
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(
        request,
        "partials/stats.html",
        {"stats": stats},
    )


@app.get("/partials/logs", response_class=HTMLResponse)
async def partial_logs(request: Request):
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(
        request,
        "partials/logs.html",
        {"stats": stats},
    )


@app.get("/partials/contacts", response_class=HTMLResponse)
async def partial_contacts(request: Request):
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(
        request,
        "partials/contacts.html",
        {"stats": stats},
    )


@app.post("/campaign/start")
async def campaign_start(request: Request):
    message = await campaign_worker.start()
    if _wants_html(request):
        stats = await get_dashboard_stats()
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/campaign/pause")
async def campaign_pause(request: Request):
    message = await campaign_worker.pause()
    if _wants_html(request):
        stats = await get_dashboard_stats()
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/campaign/resume")
async def campaign_resume(request: Request):
    message = await campaign_worker.start()
    if _wants_html(request):
        stats = await get_dashboard_stats()
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/campaign/stop")
async def campaign_stop(request: Request):
    message = await campaign_worker.stop()
    if _wants_html(request):
        stats = await get_dashboard_stats()
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/campaign/send")
async def campaign_send_one(request: Request):
    message = await campaign_worker.send_one_now()
    if _wants_html(request):
        stats = await get_dashboard_stats()
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/import")
async def import_profiles(
    request: Request,
    scrape_names: str = Form("on"),
):
    result = await import_csv(scrape_names=scrape_names == "on")
    message = (
        f"Imported {result['inserted']} contacts "
        f"(age {result['min_age']}-{result['max_age']}, valid email). "
        f"Skipped: {result['skipped_no_email']} no email, "
        f"{result['skipped_age']} age filter, "
        f"{result['duplicates']} duplicates. "
        f"Names scraped: {result['names_scraped']}."
    )
    stats = await get_dashboard_stats()
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/?imported=1", status_code=303)


@app.post("/scrape-names")
async def scrape_names_route(request: Request):
    updated = await resolve_missing_names()
    message = f"Updated {updated} contact names from profile pages."
    stats = await get_dashboard_stats()
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/template")
async def save_template(
    request: Request,
    subject: str = Form(...),
    body: str = Form(...),
):
    async with get_db() as db:
        await db.execute(
            "UPDATE email_template SET subject = ?, body = ? WHERE id = 1",
            (subject.strip(), body),
        )
        await db.commit()
    stats = await get_dashboard_stats()
    message = "Email template saved."
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/settings/daily-limit")
async def update_daily_limit(
    request: Request,
    daily_limit: int = Form(...),
):
    daily_limit = max(1, min(daily_limit, 500))
    async with get_db() as db:
        await db.execute(
            "UPDATE campaigns SET daily_limit = ? WHERE id = 1",
            (daily_limit,),
        )
        await db.commit()
    settings.daily_limit = daily_limit
    stats = await get_dashboard_stats()
    message = f"Daily limit set to {daily_limit}."
    if _wants_html(request):
        return templates.TemplateResponse(
            request,
            "partials/stats.html",
            {"stats": stats, "flash": message},
        )
    return RedirectResponse("/", status_code=303)


def _wants_html(request: Request) -> bool:
    return "HX-Request" in request.headers or "text/html" in (
        request.headers.get("accept") or ""
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
