"""T1: Config, Clock, AppError family, error handler, create_app."""
import time

import pytest

from app import create_app, errors
from app.clock import SystemClock
from app.config import Config, ConfigError
from app.errors import AppError
from tests.fakes import FakeClock

ENV = {"LECTURER_PIN": "1234", "SECRET_KEY": "s", "BASE_URL": "https://test.example"}


def test_config_defaults():
    config = Config.from_env(ENV)
    assert config.database_path == "instance/app.db"
    assert config.face_score_threshold == 0.4
    assert config.anthropic_model == "claude-sonnet-5-5"
    assert config.whisper_model == "base"
    assert config.anthropic_api_key is None  # NFR-9: no key is fine


def test_config_threshold_override():
    assert Config.from_env({**ENV, "FACE_SCORE_THRESHOLD": "0.5"}).face_score_threshold == 0.5


@pytest.mark.parametrize("name", ["LECTURER_PIN", "SECRET_KEY", "BASE_URL"])
@pytest.mark.parametrize("value", [None, ""])
def test_config_required_variables(name, value):
    env = {k: v for k, v in ENV.items() if k != name}
    if value is not None:
        env[name] = value
    with pytest.raises(ConfigError):
        Config.from_env(env)


def test_config_error_is_not_app_error():
    assert not issubclass(ConfigError, AppError)


def test_system_clock_is_close_to_time():
    assert abs(SystemClock().now() - time.time()) < 1


def test_fake_clock_moves_only_on_request():
    clock = FakeClock(10.0)
    clock.advance(5)
    assert clock.now() == 15.0
    clock.set(1.0)
    assert clock.now() == 1.0


# (class name, group base name, status, SRS message)
TABLE = [
    ("QrExpiredError", "CheckInError", 400, "This QR code has expired. Scan a fresh one."),
    ("WindowExpiredError", "CheckInError", 400, "Your check-in time ran out. Scan the QR code again."),
    ("WrongCodeError", "CheckInError", 400, "Wrong code. Type the code shown under the QR now."),
    ("TooManyAttemptsError", "CheckInError", 429, "Too many tries. Scan the QR code again."),
    ("AlreadyCheckedInError", "CheckInError", 409, "You are already checked in for this class."),
    ("SessionClosedError", "CheckInError", 409, "Attendance for this class is closed."),
    ("QrRequiredError", "CheckInError", 400, "Scan the QR code on the projector."),
    ("NoOpenSessionError", "CheckInError", 404, "There is no attendance check-in right now."),
    ("EmptyNicknameError", "CheckInError", 400, "Please choose a nickname (not your real name or ID)."),
    ("SessionAlreadyOpenError", "AppError", 409, "A session is already open. Close it first."),
    ("UnreadablePhotoError", "PhotoError", 400, "We could not read this photo. Please try another one."),
    ("DetectorUnavailableError", "PhotoError", 503, "Head count is not available right now."),
    ("EmptyCommentError", "CommentError", 400, "Please write something before sending."),
    ("CommentTooLongError", "CommentError", 400, "Please keep your comment under 500 characters."),
    ("InvalidPollError", "PollError", 400, "A poll needs a question and 2 to 4 options."),
    ("PollAlreadyOpenError", "PollError", 409, "A poll is already open. Close it first."),
    ("AlreadyVotedError", "PollError", 409, "You have already voted."),
    ("PollClosedError", "PollError", 409, "This poll is closed."),
    ("InvalidRepoUrlError", "ReviewError", 400, "Please enter a public GitHub repository link."),
    ("RepoUnavailableError", "ReviewError", 400, "We could not download this repository. Is it public?"),
    ("LLMUnavailableError", "AppError", 503, "The review service is unavailable right now. Please try again later."),
    ("UnreadableVideoError", "AppError", 400, "We could not read this video file."),
    ("WrongPinError", "AppError", 401, "Wrong PIN."),
]


def test_table_has_23_errors():
    assert len(TABLE) == 23


@pytest.mark.parametrize("name,base,status,message", TABLE)
def test_error_message_status_and_group(name, base, status, message):
    error = getattr(errors, name)()
    assert error.user_message == message
    assert error.http_status == status
    assert isinstance(error, getattr(errors, base))


def test_llm_error_summary_wording():
    error = errors.LLMUnavailableError("summary")
    assert error.user_message == "The summary service is unavailable right now. Please try again later."


@pytest.fixture
def failing_app(app):
    @app.get("/boom-app")
    def boom_app():
        raise errors.WrongCodeError()

    @app.get("/api/boom-app")
    def api_boom_app():
        raise errors.QrExpiredError()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail at /home/x/file.py")

    return app


def test_app_error_renders_message_and_status(failing_app):
    response = failing_app.test_client().get("/boom-app")
    assert response.status_code == 400
    assert "Wrong code. Type the code shown under the QR now." in response.get_data(as_text=True)


def test_app_error_under_api_is_json(failing_app):
    response = failing_app.test_client().get("/api/boom-app")
    assert response.status_code == 400
    assert response.get_json() == {"error": errors.QrExpiredError.user_message}


def test_unexpected_error_is_generic_and_logged(failing_app, caplog):
    failing_app.config["PROPAGATE_EXCEPTIONS"] = False
    response = failing_app.test_client().get("/boom")
    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "Something went wrong. Please try again." in body
    for leak in ("Traceback", "RuntimeError", "secret detail", "file.py"):
        assert leak not in body
    assert "secret detail" in caplog.text  # the traceback is in the log


def test_unknown_page_has_plain_404(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert "Traceback" not in response.get_data(as_text=True)


def test_create_app_is_not_debug_and_has_services(config, clock):
    app = create_app(config, clock=clock)
    assert app.debug is False
    assert app.extensions["services"]["clock"] is clock


def test_create_app_defaults_to_system_clock(config):
    assert isinstance(create_app(config).extensions["services"]["clock"], SystemClock)


def test_ping(client):
    response = client.get("/ping")
    assert response.status_code == 200
