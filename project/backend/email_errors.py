"""Outbound email errors — delegates to grafi_core."""

from grafi_core.email.errors import EmailNotConfiguredError, EmailSendError

__all__ = ["EmailNotConfiguredError", "EmailSendError"]
