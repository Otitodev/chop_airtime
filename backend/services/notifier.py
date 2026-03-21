"""Low-balance and alert notifications via Slack webhook and/or SMTP email."""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def send_low_balance_alert(balance: float) -> None:
    """Fire Slack and/or email notification when wallet drops below threshold."""
    settings = get_settings()
    message = (
        f"⚠️ Chop Airtime wallet LOW BALANCE alert!\n"
        f"Current balance: ₦{balance:,.2f}\n"
        f"Threshold: ₦{settings.low_balance_threshold:,.2f}\n"
        f"Please top up the wallet ASAP."
    )

    await _notify_slack(message, settings)
    _notify_email(message, settings)


async def _notify_slack(message: str, settings) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                settings.slack_webhook_url,
                json={"text": message},
            )
        if resp.status_code >= 300:
            logger.warning("Slack notification failed: %d %s", resp.status_code, resp.text)
        else:
            logger.info("Slack low-balance alert sent")
    except Exception as exc:
        logger.error("Slack notification error: %s", exc)


def _notify_email(message: str, settings) -> None:
    if not settings.smtp_host or not settings.alert_email_to:
        return
    try:
        msg = MIMEText(message)
        msg["Subject"] = "⚠️ Chop Airtime — Low Wallet Balance"
        msg["From"] = settings.smtp_user
        msg["To"] = settings.alert_email_to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, [settings.alert_email_to], msg.as_string())
        logger.info("Email low-balance alert sent to %s", settings.alert_email_to)
    except Exception as exc:
        logger.error("Email notification error: %s", exc)
