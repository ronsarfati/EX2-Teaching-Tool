"""JSON endpoints polled by the lecturer's browser (FR-1.5, FR-1.8)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from app.adapters.qr import qr_png_data_uri
from app.repositories.checkins import NetworkOrigin
from app.web.auth import lecturer_required

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/projector")
@lecturer_required
def projector():
    """QR image and 3-digit code of the open session; both null when none is open (FR-1.13)."""
    state = current_app.extensions["services"]["session_service"].projector_state()
    if state is None:
        return jsonify(open=False, qr=None, code=None)
    return jsonify(open=True, qr=qr_png_data_uri(state.check_in_url), code=state.code)


@bp.get("/sessions/<int:session_id>/attendance")
@lecturer_required
def attendance(session_id: int):
    """Live table rows and N (FR-1.14). Nicknames, times and origin labels only: no token, no IP (D21)."""
    services = current_app.extensions["services"]
    summary = services["session_service"].summary(session_id)
    return jsonify(
        open=summary.session.is_open(),
        n=summary.n,
        head_count=summary.session.head_count,  # null until a photo is counted (T11)
        consistency=summary.consistency,  # string status, null until T11
        off_campus_n=summary.origin_counts[NetworkOrigin.OFF_CAMPUS],
        apple_relay_n=summary.origin_counts[NetworkOrigin.APPLE_RELAY],
        check_ins=[
            {"nickname": c.nickname, "checked_in_at": c.checked_in_at, "network_origin": c.network_origin.value}
            for c in summary.check_ins
        ],
    )


def _poll_json(poll) -> dict:
    """Counts per option; no voter information exists to leak (D28)."""
    return {
        "id": poll.id,
        "question": poll.question,
        "open": poll.is_open,
        "total": poll.total_votes(),
        "options": [{"id": o.id, "label": o.label, "votes": o.votes} for o in poll.options],
    }


@bp.get("/polls/<int:poll_id>/results")
@lecturer_required
def poll_results(poll_id: int):
    """Live counts for the lecturer page (FR-3.3)."""
    return jsonify(_poll_json(current_app.extensions["services"]["poll_service"].get(poll_id)))


@bp.get("/poll/current")
def poll_current():
    """The open poll for students, or null; no PIN needed (FR-3.2)."""
    poll = current_app.extensions["services"]["poll_service"].current()
    return jsonify(poll=_poll_json(poll) if poll else None)


@bp.get("/comments")
@lecturer_required
def comments():
    """Newest comments first: text and time only (FR-2.2, D29)."""
    recent = current_app.extensions["services"]["comment_service"].recent()
    return jsonify(comments=[{"text": c.text, "created_at": c.created_at} for c in recent])
