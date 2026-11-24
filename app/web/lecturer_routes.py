"""Lecturer pages: login, dashboard, sessions, polls, homework peers and video summaries (FR-1, FR-3, FR-4, FR-6.1)."""
from __future__ import annotations

from flask import (Blueprint, Response, abort, current_app, redirect, render_template, request, session,
                   url_for)
from werkzeug.exceptions import RequestEntityTooLarge

from app.errors import (InvalidRepoUrlError, UnreadablePhotoError, UnsupportedVideoFormatError,
                        VideoTooLargeError, WrongPinError)
from app.repositories.summaries import JobStatus
from app.services.video import VideoSummaryService, summary_markdown, summary_plain_text
from app.timezone import format_local
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
    """Session state plus one-line summaries of the other tools, so the cards show what is going on."""
    services = _services()
    sessions = services["session_service"]
    return render_template(
        "lecturer.html", current=sessions.current(), last_session=sessions.latest(),
        poll=services["poll_service"].latest(), comment_count=services["comment_service"].count(),
        video_job=services["video_service"].active(),
    )


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


@bp.route("/sessions/<int:session_id>/photo", methods=["GET", "POST"])
@lecturer_required
def photo(session_id: int):
    """Upload or shoot a class photo, count the faces, show N / D / status (FR-1.15-FR-1.17, UC-4).

    The upload is read into memory and dropped with the request; no edit-count route exists (FR-1.17).
    """
    summary = None
    if request.method == "GET":
        _services()["session_service"].summary(session_id)  # 404 for an unknown session instead of an empty form
    else:
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


@bp.route("/polls", methods=["GET", "POST"])
@lecturer_required
def polls():
    """Create a poll (FR-3.1, UC-9) and show the latest one with live results (FR-3.3, FR-3.4)."""
    service = _services()["poll_service"]
    if request.method == "POST":
        service.create(request.form.get("question", ""), request.form.getlist("option"))
        return redirect(url_for("lecturer.polls"))
    return render_template("lecturer_poll.html", poll=service.latest())


@bp.post("/polls/<int:poll_id>/close")
@lecturer_required
def close_poll(poll_id: int):
    _services()["poll_service"].close(poll_id)
    return redirect(url_for("lecturer.polls"))


@bp.get("/comments")
@lecturer_required
def comments():
    """Page that polls /api/comments (FR-2.2, UC-8)."""
    return render_template("lecturer_comments.html")


@bp.route("/peers", methods=["GET", "POST"])
@lecturer_required
def peers():
    """Edit the comparison repositories used by the homework review (FR-5.5, OI-1); a bad line keeps the list."""
    reviewer = _services()["reviewer"]
    if request.method == "POST":
        text = request.form.get("urls", "")
        try:
            reviewer.set_peer_repos(text.splitlines())
        except InvalidRepoUrlError as error:
            return render_template("peers.html", text=text, error=error.user_message), error.http_status
        return redirect(url_for("lecturer.peers"))
    return render_template("peers.html", text="\n".join(reviewer.peer_repos()), error=None)


@bp.route("/video", methods=["GET", "POST"])
@lecturer_required
def video():
    """Upload a recording for a summary (FR-4.1, UC-12) and list the active job and past summaries (FR-4.7)."""
    services = _services()
    service = services["video_service"]
    limit = services["config"].video_max_bytes
    if request.method == "POST":
        # Raised for this request only, before the body is read: the other uploads keep the 25 MB limit.
        request.max_content_length = limit
        try:
            upload = request.files.get("video")
            language = request.form.get("language", "auto")
        except RequestEntityTooLarge:
            raise VideoTooLargeError(limit) from None
        if upload is None:
            raise UnsupportedVideoFormatError()
        job = service.submit(upload.stream, upload.filename or "", language)
        return redirect(url_for("lecturer.video_job", job_id=job.id), code=303)
    return render_template(
        "video.html", active=service.active(), recent=service.recent(10), max_bytes=limit,
        too_large_message=VideoTooLargeError(limit).user_message,
        extensions=sorted(VideoSummaryService.ALLOWED_EXTENSIONS),
    )


@bp.get("/video/jobs/<int:job_id>")
@lecturer_required
def video_job(job_id: int):
    """Status page while the job runs, the summary or the failure message once it ended (FR-4.7, FR-4.8)."""
    return render_template("video_job.html", job=_services()["video_service"].get(job_id), JobStatus=JobStatus)


@bp.post("/video/jobs/<int:job_id>/cancel")
@lecturer_required
def video_job_cancel(job_id: int):
    """Cancel the active job (D36-a); an unknown id is a 404 and a finished job is left unchanged."""
    _services()["video_service"].cancel(job_id)
    return redirect(url_for("lecturer.video_job", job_id=job_id), code=303)


def _summary_download(job_id: int, extension: str) -> Response:
    job = _services()["video_service"].get(job_id)
    if job.status is not JobStatus.DONE:
        abort(404, "This summary is not ready yet.")
    if extension == "md":
        content, mimetype = summary_markdown(job), "text/markdown"
    else:
        content, mimetype = summary_plain_text(job), "text/plain"
    day = format_local(job.finished_at or job.created_at, "%Y-%m-%d")
    response = _download(content.encode("utf-8"), f"lecture-summary-{day}-{job.id}.{extension}", mimetype)
    response.headers["Content-Type"] = f"{mimetype}; charset=utf-8"
    return response


@bp.get("/video/jobs/<int:job_id>/summary.md")
@lecturer_required
def video_summary_md(job_id: int):
    return _summary_download(job_id, "md")


@bp.get("/video/jobs/<int:job_id>/summary.txt")
@lecturer_required
def video_summary_txt(job_id: int):
    return _summary_download(job_id, "txt")
