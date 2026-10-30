"""
Weekly program reminders by email.

On Sundays, everyone who has turned reminders on, has an email address and
is in the middle of the 12-week program gets an email saying a new week
starts tomorrow, with a link to Fickologen and their next week.

A background loop started with the backend (start_scheduler) sends them on
Sunday from REMINDER_HOUR (default 18) Swedish time. Each user is "claimed"
with an atomic UPDATE before their email is sent, so the same Sunday's
reminder never goes out twice, even with several backend workers or a
restart. Admins can also send them by hand (POST /admin/reminders/send).
"""
import asyncio
import html
import os
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from ..config.database import SessionLocal
from ..models.cbt_progress import CbtProgress
from ..models.user import User
from . import email
from .program_content import PROGRAM_WEEKS, get_week

STOCKHOLM = ZoneInfo("Europe/Stockholm")
SUNDAY = 6
CHECK_INTERVAL_SECONDS = 600

_scheduler_task: asyncio.Task | None = None


def app_url() -> str:
    """Where the links in the email point: the Streamlit frontend."""
    return os.environ.get("APP_URL", "http://localhost:8501").rstrip("/")


def reminder_hour() -> int:
    return int(os.environ.get("REMINDER_HOUR", "18"))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _start_of_local_day_utc(now_utc: datetime) -> datetime:
    """Midnight today in Swedish time, as naive UTC like the database stores it."""
    local = now_utc.replace(tzinfo=timezone.utc).astimezone(STOCKHOLM)
    midnight = datetime.combine(local.date(), time(0), tzinfo=STOCKHOLM)
    return midnight.astimezone(timezone.utc).replace(tzinfo=None)


def is_reminder_time(now_utc: datetime) -> bool:
    local = now_utc.replace(tzinfo=timezone.utc).astimezone(STOCKHOLM)
    return local.weekday() == SUNDAY and local.hour >= reminder_hour()


@dataclass
class Reminder:
    subject: str
    text: str
    html: str


def build_reminder(user: User, week_number: int) -> Reminder:
    """The email for a user whose next step is week_number."""
    week = get_week(week_number)
    title = week.title if week else ""
    minutes = f" (ca {week.minutes} min)" if week and week.minutes else ""
    program_link = f"{app_url()}/?view=treatment"
    account_link = f"{app_url()}/?view=account"
    greeting = f"Hej {user.first_name}!" if user.first_name else "Hej!"
    next_step = f"Vecka {week_number}: {title}{minutes}" if title else f"Vecka {week_number}"

    text = (
        f"{greeting}\n\n"
        "Imorgon börjar en ny vecka i ditt program på Fickologen.\n\n"
        f"Ditt nästa steg: {next_step}\n\n"
        "Gå i din egen takt – det finns ingen brådska.\n\n"
        f"Öppna Fickologen: {program_link}\n\n"
        "--\n"
        "Du får det här mejlet för att du har slagit på veckopåminnelser.\n"
        f"Du kan stänga av dem när du vill under Mitt konto: {account_link}\n"
    )
    body_html = f"""\
<div style="font-family: Arial, Helvetica, sans-serif; color: #33312D; background: #FAF7F1; padding: 24px;">
  <div style="max-width: 520px; margin: 0 auto; background: #FFFFFF; border: 1px solid #EAE3D7; border-radius: 16px; padding: 28px;">
    <p style="margin: 0 0 12px 0; font-size: 16px;">{html.escape(greeting)}</p>
    <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6;">
      Imorgon börjar en ny vecka i ditt program på Fickologen.
    </p>
    <div style="background: #E7EFE8; border-radius: 12px; padding: 14px 16px; margin: 0 0 16px 0;">
      <div style="font-size: 12px; color: #5F7A69; text-transform: uppercase; letter-spacing: 0.06em;">Ditt nästa steg</div>
      <div style="font-size: 16px; font-weight: bold; color: #211F1A; margin-top: 4px;">{html.escape(next_step)}</div>
    </div>
    <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6;">Gå i din egen takt – det finns ingen brådska.</p>
    <a href="{html.escape(program_link)}" style="display: inline-block; background: #7C9885; color: #FFFFFF; text-decoration: none; padding: 12px 22px; border-radius: 12px; font-weight: bold;">Öppna Fickologen</a>
    <p style="margin: 24px 0 0 0; font-size: 12px; color: #7A7468; line-height: 1.5;">
      Du får det här mejlet för att du har slagit på veckopåminnelser.
      Du kan stänga av dem när du vill under <a href="{html.escape(account_link)}" style="color: #5F7A69;">Mitt konto</a>.
    </p>
  </div>
</div>
"""
    return Reminder(subject="Imorgon börjar en ny vecka i Fickologen", text=text, html=body_html)


def _next_week(progress: CbtProgress) -> int | None:
    """The week to remind about, or None when the whole program is done."""
    if PROGRAM_WEEKS in (progress.completed_weeks or []):
        return None
    return progress.current_week


def due_users(db: Session) -> list[tuple[User, int]]:
    """Users who should get a reminder, with the week to remind them about."""
    rows = (
        db.query(User, CbtProgress)
        .join(CbtProgress, CbtProgress.user_id == User.id)
        .filter(User.reminders_enabled.is_(True), User.email.isnot(None), User.email != "")
        .order_by(User.id)
        .all()
    )
    return [(user, week) for user, progress in rows if (week := _next_week(progress)) is not None]


@dataclass
class RunResult:
    sent: int = 0
    already_sent: int = 0
    failed: int = 0


def send_weekly_reminders(db: Session, now_utc: datetime | None = None) -> RunResult:
    """
    Sends today's reminder to every due user who has not had it yet today.

    Raises:
        email.EmailNotConfigured: if SMTP is not set up
    """
    if not email.is_configured():
        raise email.EmailNotConfigured()
    now_utc = now_utc or _utc_now()
    start_of_today = _start_of_local_day_utc(now_utc)
    result = RunResult()

    for user, week_number in due_users(db):
        previous = user.last_reminder_sent_at
        # Claim the user: only one run can move last_reminder_sent_at into today.
        claimed = db.execute(
            update(User)
            .where(
                User.id == user.id,
                or_(User.last_reminder_sent_at.is_(None), User.last_reminder_sent_at < start_of_today),
            )
            .values(last_reminder_sent_at=now_utc)
            .execution_options(synchronize_session=False)
        ).rowcount
        db.commit()
        if not claimed:
            result.already_sent += 1
            continue

        reminder = build_reminder(user, week_number)
        try:
            email.send_email(user.email, reminder.subject, reminder.text, reminder.html)
            result.sent += 1
        except Exception as exc:
            # Release the claim so the next run tries again.
            print(f"Reminder to user ID {user.id} failed: {exc!r}")
            db.execute(
                update(User)
                .where(User.id == user.id)
                .values(last_reminder_sent_at=previous)
                .execution_options(synchronize_session=False)
            )
            db.commit()
            result.failed += 1

    print(f"Weekly reminders: {result.sent} sent, {result.already_sent} already sent, {result.failed} failed")
    return result


def send_test_reminder(user: User, db: Session) -> None:
    """
    Sends the reminder to one user right away, for checking that it arrives.
    Does not count as this week's reminder.

    Raises:
        email.EmailNotConfigured: if SMTP is not set up
    """
    progress = db.query(CbtProgress).filter(CbtProgress.user_id == user.id).first()
    week_number = (_next_week(progress) if progress else None) or 1
    reminder = build_reminder(user, week_number)
    email.send_email(user.email, "[Test] " + reminder.subject, reminder.text, reminder.html)


def _run_once() -> None:
    db = SessionLocal()
    try:
        send_weekly_reminders(db)
    finally:
        db.close()


async def _scheduler_loop() -> None:
    while True:
        if is_reminder_time(_utc_now()):
            try:
                await asyncio.to_thread(_run_once)
            except Exception as exc:
                print(f"Weekly reminder run failed: {exc!r}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler() -> None:
    """
    Starts the Sunday reminder loop, unless SMTP is not configured or
    REMINDER_SCHEDULER=off (e.g. when a cron job sends them instead).
    """
    if not email.is_configured():
        print("Weekly reminders: SMTP_HOST not set, reminders are off")
        return
    if os.environ.get("REMINDER_SCHEDULER", "on").lower() == "off":
        print("Weekly reminders: scheduler turned off with REMINDER_SCHEDULER=off")
        return
    global _scheduler_task
    # Keep a reference: the event loop only holds tasks weakly.
    _scheduler_task = asyncio.get_running_loop().create_task(_scheduler_loop())
    print(f"Weekly reminders: scheduled for Sundays from {reminder_hour()}:00 Swedish time")
