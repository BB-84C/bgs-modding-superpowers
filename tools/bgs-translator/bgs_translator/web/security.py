"""Localhost shared-secret auth for CLI-to-web IPC."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Cookie, Header, HTTPException, Response, status

from bgs_translator.config import paths

COOKIE_NAME = "bgs_session"


def secret_path() -> Path:
    """Return the GUI shared-secret path."""

    return paths.translator_root() / "gui.secret"


def ensure_shared_secret() -> str:
    """Create or read the current GUI shared secret."""

    path = secret_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return value


def remove_shared_secret() -> None:
    """Remove the GUI shared-secret marker."""

    try:
        secret_path().unlink()
    except FileNotFoundError:
        pass


def issue_browser_cookie(response: Response) -> None:
    """Set the HttpOnly same-origin cookie used by browser fetch calls."""

    response.set_cookie(
        COOKIE_NAME,
        ensure_shared_secret(),
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=86400,
    )


def require_shared_secret(
    authorization: str | None = Header(None),
    bgs_session: str | None = Cookie(None),
) -> None:
    """Accept either CLI bearer auth or the browser's same-origin cookie."""

    expected = ensure_shared_secret()
    if authorization == f"Bearer {expected}":
        return
    if bgs_session == expected:
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid GUI session")


__all__ = [
    "COOKIE_NAME",
    "ensure_shared_secret",
    "issue_browser_cookie",
    "remove_shared_secret",
    "require_shared_secret",
    "secret_path",
]
