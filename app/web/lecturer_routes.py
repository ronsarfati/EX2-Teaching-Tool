"""Lecturer pages: login, dashboard, open / close session (FR-1.1, FR-1.13, FR-6.1)."""
from __future__ import annotations

from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for

from app.errors import InvalidNetworkRangeError, UnreadablePhotoError, WrongPinError
from app.services.network import NetworkPolicy
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


def _render_allow_list(text: str, error: str | None = None, status: int = 200):
    return render_template("allow_list.html", text=text, error=error), status


@bp.route("/allow-list", methods=["GET", "POST"])
@lecturer_required
def allow_list():
    """Edit the campus allow-list (FR-1.4, UC-6); an invalid line keeps the stored list (D31)."""
    policy = NetworkPolicy(_services()["settings"])
    if request.method == "POST":
        text = request.form.get("ranges", "")
        try:
            policy.save_ranges(text.splitlines())
        except InvalidNetworkRangeError as error:
            return _render_allow_list(text, error.user_message, error.http_status)  # keep what was typed
        return redirect(url_for("lecturer.allow_list"))
    return _render_allow_list("\n".join(policy.ranges()))


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


@bp.route("/sessions/<int:session_id>/photo", methods=["GET", "POST"])
@lecturer_required
def photo(session_id: int):
    """Upload or shoot a class photo, count the faces, show N / D / status (FR-1.15-FR-1.17, UC-4).

    The upload is read into memory and dropped with the request; no edit-count route exists (FR-1.17).
    """
    summary = None
    if request.method == "POST":
        upload = request.files.get("photo")
        if upload is None:
            raise UnreadablePhotoError()
        summary = _services()["session_service"].record_head_count(session_id, upload.read())
    return render_template("photo.html", session_id=session_id, summary=summary)


def _download(content: bytes, filename: str, mimetype: str) -> Response:
    return Response(content, mimetype=mimetype, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.get("/export/checkins.csv")
@lecturer_required
def export_checkins_csv():
    """All check-ins of all sessions as CSV (FR-1.18, UC-5)."""
    return _download(_services()["exporter"].checkins_csv(), "checkins.csv", "text/csv")


@bp.get("/export/summary.csv")
@lecturer_required
def export_summary_csv():
    """Per-session N, D and status as CSV (FR-1.18)."""
    return _download(_services()["exporter"].summary_csv(), "summary.csv", "text/csv")


@bp.get("/export.xlsx")
@lecturer_required
def export_xlsx():
    """Both tables as the sheets "Check-ins" and "Summary" of one workbook (FR-1.18)."""
    return _download(_services()["exporter"].xlsx(), "attendance.xlsx",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
