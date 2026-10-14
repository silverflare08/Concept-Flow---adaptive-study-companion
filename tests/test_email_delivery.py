from unittest.mock import MagicMock
from studybuddy import email_delivery


def test_disabled_email(monkeypatch):
    monkeypatch.delenv("CONCEPTFLOW_SMTP_HOST", raising=False)
    assert email_delivery.send_welcome_email({}) is False


def test_email_uses_tls_without_password_in_message(monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CONCEPTFLOW_EMAIL_FROM", "study@example.com")
    smtp = MagicMock()
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", smtp)
    assert email_delivery.send_welcome_email({"name": "Alice", "username": "alice", "email": "alice@example.com"})
    server = smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    message = server.send_message.call_args.args[0]
    assert message["To"] == "alice@example.com"
    assert "a-long-password" not in message.as_string()


def test_delivery_failure_is_nonfatal(monkeypatch):
    monkeypatch.setenv("CONCEPTFLOW_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CONCEPTFLOW_EMAIL_FROM", "study@example.com")
    smtp = MagicMock(side_effect=OSError("connection unavailable"))
    monkeypatch.setattr(email_delivery.smtplib, "SMTP", smtp)
    assert email_delivery.send_welcome_email({"name": "Alice", "username": "alice", "email": "alice@example.com"}) is False
