"""Minimal `.env` loader (stdlib only): KEY=VALUE lines, so `python -m app` works without python-dotenv."""
from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path


def _unquote(value: str) -> str:
    """Strip one pair of matching surrounding quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_env_file(path: str | os.PathLike = ".env", environ: MutableMapping[str, str] = os.environ) -> None:
    """Add variables from `path` to `environ`. Real environment variables always win; a missing file is fine.

    Values are never logged or returned: they may be secrets (API keys).
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in environ:
            environ[key] = _unquote(value.strip())
