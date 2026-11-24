"""Student pages without login: menu and attendance check-in (FR-1.7-FR-1.12, FR-6.2, UC-2, UC-3)."""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, url_for

from app.errors import InvalidPollError, NoOpenSessionError, QrRequiredError
from app.services.homework import NO_PEER_SENTENCE
from app.web.device import (
    attach_device_cookie,
    cookie_differs_from_stored,
    device_token,
    signed_current_token,
)

bp = Blueprint("student", __name__)
bp.after_app_request(attach_device_cookie)


def _services() -> dict:
    return current_app.extensions["services"]


@bp.get("/")
def menu():
    return render_template(
        "message.html",
        heading="HereOrNot",
        text="To check in, scan the QR code on the projector.",
        links=[
            ("/checkin", "Check in", "Scan the QR code on the screen", "qr"),
            ("/poll", "Poll", "Vote in the live poll", "bar-chart"),
            ("/comments", "Comments", "Send an anonymous suggestion", "message"),
            ("/review", "Homework review", "Compare two submissions", "git-branch"),
        ],
    )


@bp.post("/device/sync")
def device_sync():
    """Reconcile the cookie with the copies mirrored on the phone (D37).

    The page script sends what it found in localStorage / IndexedDB. A valid copy wins over the
    cookie (the cookie was probably deleted); `changed` tells the page to reload so that the
    QR scan window is reopened under the real identity.
    """
    payload = request.get_json(silent=True) or {}
    stored = payload.get("stored", [])
    candidates = [v for v in stored if isinstance(v, str)] if isinstance(stored, list) else []
    changed = cookie_differs_from_stored(candidates)
    g.stored_hint = candidates
    return jsonify(token=signed_current_token(), changed=changed)


@bp.get("/c/<qr_token>")
def scan(qr_token: str):
    """A QR scan: open the 1-minute window; ask for a nickname only if this device has none."""
    stored_nickname = _services()["checkin_service"].start(qr_token, device_token())
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
        device_token(), request.form.get("code", "").strip(), request.form.get("nickname")
    )
    return render_template("checked_in.html", nickname=check_in.nickname)


@bp.get("/poll")
def poll():
    """The open poll, if any. Open to every device (FR-3.2)."""
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


@bp.route("/comments", methods=["GET", "POST"])
def comments():
    """Post an anonymous comment or suggestion; no session needed, so it also works after class (FR-2.1, FR-2.3)."""
    if request.method == "POST":
        _services()["comment_service"].post(request.form.get("text", ""))
        return redirect(url_for("student.comments", sent=1))
    return render_template("comments.html", sent=request.args.get("sent") == "1")


@bp.route("/review", methods=["GET", "POST"])
def review():
    """Homework review (FR-5.1-FR-5.4, UC-13). No PIN (OI-10); the result is rendered, never stored (OI-9)."""
    result = None
    if request.method == "POST":
        result = _services()["reviewer"].review(request.form.get("url", ""))
    return render_template("review.html", result=result, no_peer=NO_PEER_SENTENCE)
