"""Student pages without login: menu and attendance check-in (FR-1.7-FR-1.12, FR-6.2, UC-2, UC-3)."""
from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from app.errors import InvalidPollError, NoOpenSessionError, QrRequiredError
from app.web.device import attach_device_cookie, client_ip, device_token

bp = Blueprint("student", __name__)
bp.after_app_request(attach_device_cookie)


def _services() -> dict:
    return current_app.extensions["services"]


@bp.get("/")
def menu():
    return render_template(
        "message.html",
        heading="Teaching tool",
        text="To check in, scan the QR code on the projector.",
        link_url="/checkin",
        link_text="Check in",
    )


@bp.get("/c/<qr_token>")
def scan(qr_token: str):
    """A QR scan: open the 1-minute window; ask for a nickname only if this device has none."""
    stored_nickname = _services()["checkin_service"].start(qr_token, device_token(), client_ip())
    return render_template("checkin.html", needs_nickname=stored_nickname is None)


@bp.get("/checkin")
def checkin_without_token():
    """Reached from the menu: there is nothing to confirm without a scan."""
    if _services()["session_service"].current() is None:
        raise NoOpenSessionError()
    raise QrRequiredError()


@bp.post("/checkin")
def confirm():
    check_in = _services()["checkin_service"].confirm(
        device_token(), client_ip(), request.form.get("code", "").strip(), request.form.get("nickname")
    )
    return render_template("checked_in.html", nickname=check_in.nickname)


@bp.get("/poll")
def poll():
    """The open poll, if any. No allow-list here: the design only restricts check-in to the campus (FR-3.2)."""
    return render_template("poll.html", poll=_services()["poll_service"].current(),
                           voted=request.args.get("voted") == "1")


@bp.post("/poll/vote")
def vote():
    try:
        poll_id, option_id = int(request.form["poll_id"]), int(request.form["option_id"])
    except (KeyError, ValueError):
        raise InvalidPollError() from None
    _services()["poll_service"].vote(poll_id, option_id, device_token())
    return redirect(url_for("student.poll", voted=1))
