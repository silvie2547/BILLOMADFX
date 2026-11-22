"""Transactional email: sign-up codes, password-reset codes, 2FA notices.

When SMTP is configured the messages are delivered to the user's inbox.
Without SMTP the send functions return False and the API falls back to
"display mode" — the one-time code is returned in the HTTP response and the
app shows it with a clear notice. That keeps self-hosted installs and local
development usable without pretending an email was sent.
"""
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger("billomadfx.email")


def email_delivery_enabled() -> bool:
    return settings.email_enabled and bool(settings.smtp_host)


def _send(to: str, subject: str, body: str) -> bool:
    if not email_delivery_enabled():
        log.info("SMTP not configured; would send %r to %s", subject, to)
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(message)
        return True
    except Exception:
        log.exception("Email delivery to %s failed", to)
        return False


def _code_body(purpose_line: str, code: str, ttl_minutes: int) -> str:
    return (
        "BILLOMADFX — Gold Trading Platform\n"
        "\n"
        f"{purpose_line}\n"
        "\n"
        f"Your one-time code: {code}\n"
        "\n"
        f"This code expires {ttl_minutes} minutes after it was issued and can "
        "be used once. If you did not request it, ignore this email — your "
        "account stays protected.\n"
        "\n"
        "BILLOMADFX never sends broker orders. This address does not accept replies."
    )


def send_verification_code(to: str, code: str, ttl_minutes: int) -> bool:
    return _send(
        to,
        f"BILLOMADFX verification code (expires in {ttl_minutes} min)",
        _code_body("Confirm your email address to activate your account.", code, ttl_minutes),
    )


def send_password_reset_code(to: str, code: str, ttl_minutes: int) -> bool:
    return _send(
        to,
        f"BILLOMADFX password reset code (expires in {ttl_minutes} min)",
        _code_body("Use this code to set a new password for your account.", code, ttl_minutes),
    )


def send_2fa_enabled_notice(to: str) -> bool:
    return _send(
        to,
        "BILLOMADFX two-step authentication enabled",
        "BILLOMADFX — Gold Trading Platform\n"
        "\n"
        "Two-step authentication is now active on your account. Sign-in now "
        "requires a code from your authenticator app (or one of your backup "
        "codes).\n"
        "\n"
        "If you did not enable this, sign in and disable two-step "
        "authentication immediately, then change your password.\n"
    )
