"""Lecturer PIN gate (FR-6.1, D22): the PIN lives in an env var, a successful login sets a session-cookie flag."""
from __future__ import annotations

import hmac
from functools import wraps
from typing import Callable

from flask import abort, redirect, request, session, url_for


def pin_matches(candidate: str, expected: str) -> bool:
    """Constant-time comparison so response time does not leak how many digits are right."""
    return hmac.compare_digest(candidate.encode(), expected.encode())  # bytes: compare_digest rejects non-ASCII str


def lecturer_required(view: Callable) -> Callable:
    """Redirect to the login page (401 for /api/ polls, which cannot follow a page) unless the PIN was entered."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("lecturer"):
            if request.path.startswith("/api/"):
                abort(401, "Please log in as lecturer.")
            return redirect(url_for("lecturer.login"))
        return view(*args, **kwargs)

    return wrapper
