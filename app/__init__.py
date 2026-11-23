"""Composition root: `create_app` builds the Flask app and its error handling (D2, D23)."""
from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.clock import Clock, SystemClock
from app.config import Config
from app.db import Database
from app.errors import AppError
from app.repositories.checkins import CheckInRepository
from app.repositories.sessions import SessionRepository
from app.repositories.settings import SettingsRepository
from app.repositories.windows import CheckInWindowRepository

GENERIC_MESSAGE = "Something went wrong. Please try again."
logger = logging.getLogger(__name__)


def create_app(config: Config, *, clock: Clock | None = None, **fakes: object) -> Flask:
    """Build the app. Anything left out (clock, adapters) gets its real implementation.

    `fakes` is where later tasks add head_counter, llm, fetcher and transcriber; tests inject doubles there.
    """
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.secret_key, DEBUG=False)  # NFR-8: never debug
    db = Database(config.database_path)
    db.init_schema()
    app.extensions["services"] = {
        "config": config,
        "clock": clock or SystemClock(),
        "db": db,
        "sessions": SessionRepository(db),
        "check_ins": CheckInRepository(db),
        "windows": CheckInWindowRepository(db),
        "settings": SettingsRepository(db),
        **fakes,
    }

    @app.get("/ping")
    def ping() -> str:
        return "ok"

    _register_error_handlers(app)
    return app


def _render_error(message: str, status: int):
    """JSON under /api/ (polled by scripts), a page otherwise."""
    if request.path.startswith("/api/"):
        return jsonify(error=message), status
    return render_template("error.html", message=message), status


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        return _render_error(error.user_message, error.http_status)

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        if isinstance(error, HTTPException):  # 404, 405...: keep the status, use plain wording
            return _render_error(error.description or GENERIC_MESSAGE, error.code or 500)
        logger.exception("Unhandled error on %s", request.path)  # traceback goes to the log only
        return _render_error(GENERIC_MESSAGE, 500)
