# Email Bot

FastAPI + HTMX dashboard that imports `profiles.csv`, filters contacts (age 28–45 + valid email), scrapes names from profile URLs, and sends template emails one-at-a-time with random 4–15 minute delays.

## Setup

```bash
cd "d:\Projects\Sandy\email bot"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your SMTP settings (Gmail app password recommended):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=you@gmail.com
DAILY_LIMIT=50
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000

## Workflow

1. **Import & Filter CSV** — keeps only rows with a valid email and age 28–45; scrapes Name from each `profile_url`.
2. Edit the **email template** (`{{name}}`, `{{email}}`, `{{age}}`, etc.).
3. Set **daily limit** (50 or 100).
4. Click **Start** — sends one email, waits a random 4–15 minutes, then continues.
5. Use **Pause / Resume / Stop** as needed. Progress is saved in SQLite (`data/email_bot.db`).

## Filters

| Rule | Behavior |
|------|----------|
| Email required | Invalid / empty / "SharedPrivately" skipped |
| Age 28–45 | Computed from `birthday` |
| Duplicates | Same email only imported once |

## Campaign rules (from roadmap)

- One email at a time
- Random delay (20–30 min) after each successful send
- One retry after a longer wait on failure
- Auto-pause at daily limit; counter resets next day
- Resume from first Pending/Retry contact after restart
