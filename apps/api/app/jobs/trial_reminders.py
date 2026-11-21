"""Optional 48-hour trial renewal email job.

Run via a reliable scheduler at least every 15 minutes:
  PYTHONPATH=apps/api python -m app.jobs.trial_reminders

Only opt-in accounts with verified email are contacted. Never imply a
two-day reminder is guaranteed unless the job and SMTP delivery are healthy.
"""
from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import timezone

import asyncpg


def _send_email(to: str, subject: str, body: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_SSL_PORT", "465"))
    sender = os.environ["SMTP_FROM_EMAIL"]
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=12) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)


async def run():
    if os.environ.get("TRIAL_REMINDER_JOB_ENABLED") != "true":
        raise RuntimeError("Reminders are disabled until the job is operationally verified")
    required = ("DATABASE_URL", "SMTP_HOST", "SMTP_FROM_EMAIL", "SMTP_USERNAME", "SMTP_PASSWORD")
    if any(not os.environ.get(name) for name in required):
        raise RuntimeError("Reminder service credentials are missing")
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            # Jobs are short; recoverable failed sends delete their reservation
            # for the next run. Cron execution is externally monitored.
            candidates = await conn.fetch(
                """SELECT s.id AS subscription_id,s.trial_end,u.email
                   FROM subscriptions s JOIN users u ON u.id=s.user_id
                   WHERE s.status='trialing'
                     AND s.environment='production'
                     AND s.trial_end BETWEEN now()+interval '24 hours'
                                         AND now()+interval '48 hours'
                     AND u.trial_reminder_opt_in=true
                     AND u.email IS NOT NULL
                     AND u.deleted_at IS NULL
                   ORDER BY s.trial_end LIMIT 200"""
            )
            for item in candidates:
                event_id = await conn.fetchval(
                    """INSERT INTO trial_reminder_deliveries(subscription_id,trial_end)
                       VALUES($1,$2)
                       ON CONFLICT(subscription_id,trial_end) DO NOTHING
                       RETURNING subscription_id""",
                    item["subscription_id"], item["trial_end"],
                )
                if not event_id:
                    continue
                end = item["trial_end"].astimezone(timezone.utc)
                body = (
                    "Assalamu alaikum,\n\n"
                    "Your 7-day Al-Mu'allim Pro trial is approaching its renewal on "
                    + end.strftime("%d %B %Y at %H:%M UTC")
                    + ". If you do not wish to continue, you can cancel in your "
                      "original App Store, Google Play or web billing account "
                      "before the renewal. The renewal price is the amount "
                      "displayed when you subscribed.\n\n"
                      "The full Qur'an, translations, recitations and your "
                      "free Noor plan remain available without Pro.\n\n"
                      "Al-Mu'allim"
                )
                try:
                    await asyncio.to_thread(
                        _send_email, item["email"], "Al-Mu'allim trial reminder", body,
                    )
                except Exception:
                    await conn.execute(
                        """DELETE FROM trial_reminder_deliveries
                           WHERE subscription_id=$1 AND trial_end=$2
                             AND sent_at IS NULL""",
                        item["subscription_id"], item["trial_end"],
                    )
                    raise
                else:
                    await conn.execute(
                        """UPDATE trial_reminder_deliveries
                           SET sent_at=now()
                           WHERE subscription_id=$1 AND trial_end=$2""",
                        item["subscription_id"], item["trial_end"],
                    )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
