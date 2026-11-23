"""Lecturer pages: login, dashboard, open / close session (FR-1.1, FR-1.13, FR-6.1)."""
from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app.errors import WrongPinError
from app.web.auth import lecturer_required, pin_matches

bp = Blueprint("lecturer", __name__, url_prefix="/lecturer")


def _services() -> dict:
    return current_app.extensions["services"]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not pin_matches(request.form.get("pin", ""), _services()["config"].lecturer_pin):
            raise WrongPinError()
        session["lecturer"] = True
        return redirect(url_for("lecturer.dashboard"))
    return render_template("login.html")


@bp.get("")
@lecturer_required
def dashboard():
    return render_template("lecturer.html", current=_services()["session_service"].current())


@bp.get("/projector")
@lecturer_required
def projector():
    return render_template("projector.html")


@bp.post("/sessions")
@lecturer_required
def open_session():
    _services()["session_service"].open_session()
    return redirect(url_for("lecturer.projector"))  # SD-1: the lecturer's browser is the projector


@bp.post("/sessions/close")
@lecturer_required
def close_session():
    _services()["session_service"].close_session()
    return redirect(url_for("lecturer.dashboard"))
