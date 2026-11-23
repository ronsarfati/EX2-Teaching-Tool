"""Entry point: `python -m app` serves the app on all interfaces (the tunnel or LAN reaches it)."""
from __future__ import annotations

import os
import sys

from app import create_app
from app.config import Config, ConfigError
from app.env_file import load_env_file


def main() -> None:
    load_env_file()  # only here, never in create_app: tests must not read a real .env
    try:
        config = Config.from_env(os.environ)
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}. See .env.example.")
    # debug stays off (NFR-8): the Werkzeug debugger would allow remote code execution
    create_app(config).run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)


if __name__ == "__main__":
    main()
