"""Optional SMTP welcome emails. Secrets belong in ignored environment settings."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def welcome_email_configured():
    return bool(os.getenv("CONCEPTFLOW_SMTP_HOST") and os.getenv("CONCEPTFLOW_EMAIL_FROM"))


def send_welcome_email(user):
    if not welcome_email_configured():
        return False
    message = EmailMessage()
    message["From"] = os.environ["CONCEPTFLOW_EMAIL_FROM"]
    message["To"] = user["email"]
    message["Subject"] = "Welcome to ConceptFlow"
    message.set_content(
        f"Hello {user['name']},\n\nYour ConceptFlow account @{user['username']} is ready. "
        "Sign in to organise your material and start studying.\n\n"
        "This is a welcome message, not email verification. "
        "If you did not create this account, you may ignore this message.\n\nConceptFlow"
    )
    try:
        # Always require TLS; never send login credentials over plaintext SMTP.
        with smtplib.SMTP(os.environ["CONCEPTFLOW_SMTP_HOST"],
                          int(os.getenv("CONCEPTFLOW_SMTP_PORT", "587")), timeout=10) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            username = os.getenv("CONCEPTFLOW_SMTP_USERNAME")
            if username:
                server.login(username, os.environ["CONCEPTFLOW_SMTP_PASSWORD"])
            server.send_message(message)
        return True
    except Exception as error:
        # Do not log recipient addresses, passwords or SMTP server response text.
        logger.warning("Welcome email delivery failed (%s). Account remains active.", type(error).__name__)
        return False
