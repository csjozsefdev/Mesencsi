"""Outbound email errors — separate from HTTP layer so routers can map them cleanly."""


class EmailNotConfiguredError(RuntimeError):
    """SMTP is required on this deployment but mandatory env vars are missing."""


class EmailSendError(RuntimeError):
    """SMTP is configured but message delivery failed."""
