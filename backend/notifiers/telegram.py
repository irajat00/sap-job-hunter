"""
Telegram notifications — free, via Telegram's Bot API.

Setup:
    1. Message @BotFather on Telegram, run /newbot, copy the token it gives you.
    2. Message your new bot anything (so it's allowed to message you back).
    3. Get your chat_id: visit
       https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
       and read "chat":{"id": ...} from the JSON.
    4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env

Never hardcode credentials -- both are read from the environment (via
.env, see app/env.py) at call time, not cached at import time, so tests
can monkeypatch os.environ and see it take effect immediately.

Telegram is the primary feature: every NEW qualifying SAP job collected
gets its own immediate Telegram message, in the exact format required:

    🚨 New SAP Job Found!

    Title:
    <job title>
    Company:
    <company>
    Location:
    <location>
    Posted:
    <posted date>

    Open Job:
    <url>

collectors/runner.py is responsible for the persisted `telegram_notified`
flag that prevents ever resending a notification for the same job --
this module only sends whatever it's told to send.
"""
import os
import app.env  # noqa: F401  (loads .env as an import side effect, before the os.getenv calls below)
import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _credentials():
    """Read fresh from the environment on every call (not module-level
    constants) so .env changes and test monkeypatching both take effect
    without needing to reload this module."""
    return os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")


def _send(text: str) -> bool:
    token, chat_id = _credentials()
    if not token or not chat_id:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. "
            "See notifiers/telegram.py docstring for setup steps."
        )
    resp = requests.post(
        API_URL.format(token=token),
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return True


def format_job_message(job: dict) -> str:
    """Builds the exact notification format required."""
    title = job.get("title") or "Untitled role"
    company = job.get("company") or "Unknown company"
    location = job.get("location") or "Unknown location"
    posted = job.get("posted_date") or "Unknown"
    url = job.get("job_url") or ""

    return (
        "🚨 New SAP Job Found!\n\n"
        "Title:\n"
        f"{title}\n"
        "Company:\n"
        f"{company}\n"
        "Location:\n"
        f"{location}\n"
        "Posted:\n"
        f"{posted}\n\n"
        "Open Job:\n"
        f"{url}"
    )


def notify_job(job: dict) -> bool:
    """
    Sends one Telegram message for one job, in the required format.
    Returns True on success. Raises on failure (caller decides whether
    to log-and-continue or propagate) -- callers should NOT mark a job
    as telegram_notified unless this returns True / doesn't raise.
    """
    return _send(format_job_message(job))


def notify(jobs: list[dict], summary: dict = None) -> int:
    """
    Sends an individual Telegram message per job in `jobs` (each already
    pre-filtered by the caller to "new this run" -- see
    collectors/runner.py). Returns the number of messages sent
    successfully. Each job is sent independently so one bad job/network
    blip doesn't block notifications for the rest.
    """
    sent = 0
    for job in jobs:
        notify_job(job)
        sent += 1
    return sent


# --- Daily summary (additive; run once/day by scripts/daily_summary.py
# via .github/workflows/daily-summary.yml, entirely separate from the
# per-job instant notifications above, which are unmodified) ---------

def format_daily_summary_message(stats: dict) -> str:
    """Builds the one-per-day digest message. `stats` comes from
    scripts/daily_summary.py's build_stats()."""
    return (
        "📊 Daily SAP Job Summary\n\n"
        f"Date: {stats.get('date', 'Unknown')}\n"
        f"New jobs found today: {stats.get('new_today', 0)}\n"
        f"Notifications sent today: {stats.get('notified_today', 0)}\n"
        f"Total jobs in database: {stats.get('total_jobs', 0)}"
    )


def send_daily_summary(stats: dict) -> bool:
    """Sends the ONE daily digest message. Returns True on success."""
    return _send(format_daily_summary_message(stats))
