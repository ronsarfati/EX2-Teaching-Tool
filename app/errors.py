"""User-facing exceptions. Each carries the exact SRS section 5 message and an HTTP status (D23).

Messages never contain an identifier, token, path or exception name. Group bases come first so
callers can catch a whole family (e.g. every check-in refusal).
"""
from __future__ import annotations


class AppError(Exception):
    """Base of every error shown to a user."""

    user_message: str = "Something went wrong. Please try again."
    http_status: int = 400

    def __init__(self) -> None:
        super().__init__(self.user_message)


class CheckInError(AppError):
    """A student check-in was refused."""


class PhotoError(AppError):
    """The photo head count failed."""


class CommentError(AppError):
    """A comment was refused."""


class PollError(AppError):
    """A poll action was refused."""


class ReviewError(AppError):
    """A homework review input could not be used."""


class LLMUnavailableError(AppError):
    """The LLM cannot be used (no key, network or SDK error). `feature` only changes the wording."""

    http_status = 503

    def __init__(self, feature: str = "review") -> None:
        self.feature = feature
        self.user_message = f"The {feature} service is unavailable right now. Please try again later."
        super().__init__()


class QrExpiredError(CheckInError):
    user_message = "This QR code has expired. Scan a fresh one."
    http_status = 400


class WindowExpiredError(CheckInError):
    user_message = "Your check-in time ran out. Scan the QR code again."
    http_status = 400


class WrongCodeError(CheckInError):
    user_message = "Wrong code. Type the code shown under the QR now."
    http_status = 400


class TooManyAttemptsError(CheckInError):
    user_message = "Too many tries. Scan the QR code again."
    http_status = 429


class AlreadyCheckedInError(CheckInError):
    user_message = "You are already checked in for this class."
    http_status = 409


class SessionClosedError(CheckInError):
    user_message = "Attendance for this class is closed."
    http_status = 409


class QrRequiredError(CheckInError):
    user_message = "Scan the QR code on the projector."
    http_status = 400


class NoOpenSessionError(CheckInError):
    user_message = "There is no attendance check-in right now."
    http_status = 404


class EmptyNicknameError(CheckInError):
    user_message = "Please choose a nickname (not your real name or ID)."
    http_status = 400


class SessionAlreadyOpenError(AppError):
    user_message = "A session is already open. Close it first."
    http_status = 409


class UnreadablePhotoError(PhotoError):
    user_message = "We could not read this photo. Please try another one."
    http_status = 400


class DetectorUnavailableError(PhotoError):
    user_message = "Head count is not available right now."
    http_status = 503


class EmptyCommentError(CommentError):
    user_message = "Please write something before sending."
    http_status = 400


class CommentTooLongError(CommentError):
    user_message = "Please keep your comment under 500 characters."
    http_status = 400


class InvalidPollError(PollError):
    user_message = "A poll needs a question and 2 to 4 options."
    http_status = 400


class PollAlreadyOpenError(PollError):
    user_message = "A poll is already open. Close it first."
    http_status = 409


class AlreadyVotedError(PollError):
    user_message = "You have already voted."
    http_status = 409


class PollClosedError(PollError):
    user_message = "This poll is closed."
    http_status = 409


class InvalidRepoUrlError(ReviewError):
    user_message = "Please enter a public GitHub repository link."
    http_status = 400


class RepoUnavailableError(ReviewError):
    user_message = "We could not download this repository. Is it public?"
    http_status = 400


class VideoError(AppError):
    """A recording or its summary job was refused or failed (F4, D34)."""


class UnreadableVideoError(VideoError):
    user_message = "We could not read this video file."
    http_status = 400


class UnsupportedVideoFormatError(VideoError):
    user_message = "Please choose a video or audio recording (for example MP4, MOV, MKV, WebM or M4A)."
    http_status = 400


class VideoTooLargeError(VideoError):
    """The upload is above `VIDEO_MAX_BYTES`; the message quotes the configured limit in GB."""

    http_status = 413

    def __init__(self, limit_bytes: int = 2 * 1024**3) -> None:
        self.limit_bytes = limit_bytes
        gigabytes = round(limit_bytes / 1024**3, 1)
        figure = f"{gigabytes:.0f}" if gigabytes == int(gigabytes) else f"{gigabytes:.1f}"
        self.user_message = f"This file is too large. The maximum is {figure} GB."
        super().__init__()


class NoSpeechError(VideoError):
    user_message = "No speech was found in this recording."
    http_status = 400


class TranscriptionUnavailableError(VideoError):
    user_message = "The transcription service is unavailable right now. Please try again later."
    http_status = 503


class SummaryJobRunningError(VideoError):
    user_message = "A video is already being summarised. Please wait until it is finished."
    http_status = 409


class WrongPinError(AppError):
    user_message = "Wrong PIN."
    http_status = 401
