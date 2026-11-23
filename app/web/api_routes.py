"""JSON endpoints polled by the lecturer's browser (FR-1.5, FR-1.8)."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from app.adapters.qr import qr_png_data_uri
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
    """Live table rows and N (FR-1.14). Nicknames and times only: no token, no IP (D21)."""
    services = current_app.extensions["services"]
    summary = services["session_service"].summary(session_id)
    return jsonify(
        open=summary.session.is_open(),
        n=summary.n,
        head_count=summary.session.head_count,  # null until a photo is counted (T11)
        consistency=summary.consistency,  # string status, null until T11
        check_ins=[{"nickname": c.nickname, "checked_in_at": c.checked_in_at} for c in summary.check_ins],
    )
