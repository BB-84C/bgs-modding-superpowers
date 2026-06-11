"""JSON envelope models and exit-code mapping for CLI responses."""

# TODO(Chunk-B): Keep the envelope stable as later CLI commands come online.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Envelope(BaseModel):
    """Standard machine-readable CLI response envelope."""

    ok: bool
    data: dict[str, Any] | None
    error: dict[str, Any] | None


def success(data: dict[str, Any]) -> Envelope:
    """Create a successful CLI envelope with payload data."""
    return Envelope(ok=True, data=data, error=None)


def failure(code: str, message: str, **extra: Any) -> Envelope:
    """Create a failure envelope with a stable code, message, and optional details."""
    return Envelope(ok=False, data=None, error={"code": code, "message": message, **extra})


def exit_code_for(envelope: Envelope) -> int:
    """Return the process exit code associated with an envelope."""
    if envelope.ok:
        return 0

    raw_code = None if envelope.error is None else envelope.error.get("code")
    code = raw_code if isinstance(raw_code, str) else None
    mapping = {
        "usage_error": 1,
        "validation_error": 2,
        "config_error": 3,
        "provider_error": 4,
        "io_error": 5,
        "internal_error": 10,
    }
    if code is None:
        return 1
    return mapping.get(code, 1)


__all__ = ["Envelope", "exit_code_for", "failure", "success"]
