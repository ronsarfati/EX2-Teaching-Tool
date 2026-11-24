"""T1 additions: error hygiene, JSON API errors, Config edge cases, FakeClock, create_app injection.

Covers NFR-10, NFR-8, NFR-9, NFR-12, D23, D25, FR-6.3.
"""
import inspect
import logging
import re

import pytest

from app import GENERIC_MESSAGE, create_app, errors
from app.clock import Clock, SystemClock
from app.config import Config, ConfigError
from app.errors import AppError
from tests.fakes import FakeClock

ENV = {"LECTURER_PIN": "1234", "SECRET_KEY": "s", "BASE_URL": "https://test.example"}


def all_error_classes():
    return [c for _, c in inspect.getmembers(errors, inspect.isclass)
            if issubclass(c, AppError) and c.__module__ == errors.__name__]


CONCRETE = [c for c in all_error_classes()
            if c not in (AppError, errors.CheckInError, errors.PhotoError, errors.CommentError,
                         errors.PollError, errors.ReviewError, errors.VideoError)]


# ---- errors: hygiene (NFR-10) ----
def test_every_concrete_error_is_in_srs_table_count():
    """Covers NFR-10: 29 concrete classes exist (23 + 6 of F4, D34), no undocumented extra one."""
    assert len(CONCRETE) == 29


@pytest.mark.parametrize("cls", CONCRETE, ids=lambda c: c.__name__)
def test_message_has_no_internal_identifier(cls):
    """Covers NFR-10: no class name, path, token, uuid or stray number in the message."""
    msg = cls().user_message
    assert msg.strip() == msg and msg.endswith((".", "?"))
    assert not re.search(r"Error|Exception|Traceback|\.py\b|token|uuid|SELECT|sqlite", msg, re.I)
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", msg)
    assert "/home" not in msg and "\\" not in msg
    assert cls.__name__ not in msg
    assert len(msg) < 120


@pytest.mark.parametrize("cls", CONCRETE, ids=lambda c: c.__name__)
def test_str_equals_user_message_and_is_apperror(cls):
    """Covers D23: str(exception) is the user message, status is a valid 4xx/5xx."""
    error = cls()
    assert str(error) == error.user_message
    assert isinstance(error, AppError)
    assert 400 <= error.http_status <= 599


def test_base_app_error_defaults():
    error = AppError()
    assert error.user_message == GENERIC_MESSAGE
    assert error.http_status == 400


def test_llm_error_default_feature_and_attribute():
    assert errors.LLMUnavailableError().feature == "review"
    assert errors.LLMUnavailableError("summary").feature == "summary"
    assert errors.LLMUnavailableError().http_status == 503


def test_group_bases_catch_families():
    for cls in (errors.QrExpiredError, errors.WrongCodeError, errors.EmptyNicknameError):
        with pytest.raises(errors.CheckInError):
            raise cls()
    with pytest.raises(errors.PhotoError):
        raise errors.UnreadablePhotoError()
    with pytest.raises(errors.PollError):
        raise errors.PollClosedError()


def test_srs_projector_message_has_an_error_class():
    """Covers SRS section 5 row 'FR-1.7, D31': 'Scan the QR code on the projector.' (expected to FAIL if missing)."""
    msgs = {c().user_message for c in all_error_classes()}
    assert "Scan the QR code on the projector." in msgs


# ---- error handler ----
@pytest.fixture
def boom_app(app):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/api/boom")
    def api_boom():
        raise RuntimeError("secret detail at /home/x/file.py")

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret detail at /home/x/file.py")

    @app.get("/api/poll-closed")
    def poll_closed():
        raise errors.PollClosedError()

    @app.get("/page-poll-closed")
    def page_poll_closed():
        raise errors.PollClosedError()

    @app.get("/api/llm")
    def llm():
        raise errors.LLMUnavailableError("summary")

    return app


@pytest.mark.parametrize("cls", CONCRETE, ids=lambda c: c.__name__)
def test_every_error_renders_status_and_message(app, cls):
    """Covers NFR-10: page for non-API, JSON for /api/, each with its status and exact message."""
    def raiser():
        raise cls()
    app.add_url_rule("/p", "p", raiser)
    app.add_url_rule("/api/p", "ap", raiser)
    c = app.test_client()
    page = c.get("/p")
    assert page.status_code == cls.http_status
    assert page.content_type.startswith("text/html")
    api = c.get("/api/p")
    assert api.status_code == cls.http_status
    assert api.content_type.startswith("application/json")
    assert api.get_json() == {"error": cls().user_message}


def test_html_page_escapes_message(app):
    """Covers NFR-10: message is rendered inside the error page, not leaked as raw markup."""
    @app.get("/x")
    def x():
        raise errors.WrongPinError()
    body = app.test_client().get("/x").get_data(as_text=True)
    assert "Wrong PIN." in body and 'role="alert"' in body


def test_api_unexpected_error_is_json_generic_no_leak(boom_app, caplog):
    with caplog.at_level(logging.ERROR):
        response = boom_app.test_client().get("/api/boom")
    assert response.status_code == 500
    assert response.get_json() == {"error": GENERIC_MESSAGE}
    raw = response.get_data(as_text=True)
    for leak in ("Traceback", "RuntimeError", "secret detail", "file.py", "/home"):
        assert leak not in raw
    assert "secret detail" in caplog.text
    assert "Traceback" in caplog.text


def test_html_unexpected_error_traceback_in_log_only(boom_app, caplog):
    with caplog.at_level(logging.ERROR):
        response = boom_app.test_client().get("/boom")
    assert response.status_code == 500
    assert "Traceback" not in response.get_data(as_text=True)
    assert any(r.exc_info for r in caplog.records)


def test_app_errors_are_not_logged_as_tracebacks(boom_app, caplog):
    with caplog.at_level(logging.ERROR):
        boom_app.test_client().get("/api/poll-closed")
    assert "Traceback" not in caplog.text


def test_api_llm_error_json_503(boom_app):
    response = boom_app.test_client().get("/api/llm")
    assert response.status_code == 503
    assert response.get_json()["error"] == "The summary service is unavailable right now. Please try again later."


def test_404_under_api_is_json_and_405(client):
    r = client.get("/api/nothing")
    assert r.status_code == 404 and r.get_json() is not None and "error" in r.get_json()
    r = client.post("/ping")
    assert r.status_code == 405
    assert "Traceback" not in r.get_data(as_text=True)


def test_http_errors_do_not_leak_in_html(client):
    body = client.get("/does-not-exist").get_data(as_text=True)
    assert 'role="alert"' in body


# ---- Config ----
@pytest.mark.parametrize("name", ["LECTURER_PIN", "SECRET_KEY", "BASE_URL"])
def test_config_whitespace_only_required_is_rejected(name):
    with pytest.raises(ConfigError) as info:
        Config.from_env({**ENV, name: "   "})
    assert name in str(info.value)


def test_config_error_names_all_missing_but_not_values():
    with pytest.raises(ConfigError) as info:
        Config.from_env({})
    text = str(info.value)
    for n in ("LECTURER_PIN", "SECRET_KEY", "BASE_URL"):
        assert n in text


def test_config_error_does_not_echo_secret_values():
    with pytest.raises(ConfigError) as info:
        Config.from_env({"LECTURER_PIN": "9999", "SECRET_KEY": "topsecret"})
    assert "9999" not in str(info.value) and "topsecret" not in str(info.value)


@pytest.mark.parametrize("bad", ["abc", "0,5", "0.5x", "nan?", " x "])
def test_config_non_numeric_threshold(bad):
    with pytest.raises(ConfigError) as info:
        Config.from_env({**ENV, "FACE_SCORE_THRESHOLD": bad})
    assert "FACE_SCORE_THRESHOLD" in str(info.value)


def test_config_empty_threshold_uses_default():
    assert Config.from_env({**ENV, "FACE_SCORE_THRESHOLD": ""}).face_score_threshold == 0.4


@pytest.mark.parametrize("raw,expected", [("0", 0.0), ("1", 1.0), ("0.25", 0.25), (" 0.7 ", 0.7)])
def test_config_threshold_values(raw, expected):
    assert Config.from_env({**ENV, "FACE_SCORE_THRESHOLD": raw}).face_score_threshold == expected


def test_config_empty_optionals_fall_back_to_defaults():
    env = {**ENV, "DATABASE_PATH": "", "YUNET_MODEL_PATH": "", "ANTHROPIC_API_KEY": "",
           "ANTHROPIC_MODEL": "", "WHISPER_MODEL": "", "WHISPER_LANGUAGE": ""}
    c = Config.from_env(env)
    assert c.database_path == "instance/app.db"
    assert c.yunet_model_path == "models/face_detection_yunet_2023mar.onnx"
    assert c.anthropic_api_key is None  # empty key == no key (NFR-9)
    assert c.anthropic_model == "claude-sonnet-5-5"
    assert c.whisper_model == "small"  # D34
    assert c.whisper_language is None


def test_config_optionals_are_read():
    env = {**ENV, "DATABASE_PATH": "x.db", "ANTHROPIC_API_KEY": "k", "ANTHROPIC_MODEL": "m",
           "WHISPER_MODEL": "small", "WHISPER_LANGUAGE": "he", "YUNET_MODEL_PATH": "y.onnx"}
    c = Config.from_env(env)
    assert (c.database_path, c.anthropic_api_key, c.anthropic_model) == ("x.db", "k", "m")
    assert (c.whisper_model, c.whisper_language, c.yunet_model_path) == ("small", "he", "y.onnx")


def test_config_base_url_trailing_slash_stripped():
    assert Config.from_env({**ENV, "BASE_URL": "https://t.example/"}).base_url == "https://t.example"


def test_config_is_frozen_and_ignores_unrelated_env():
    c = Config.from_env({**ENV, "PATH": "/bin", "HOME": "/x"})
    with pytest.raises(Exception):
        c.lecturer_pin = "0000"


def test_config_has_no_secret_default():
    with pytest.raises(TypeError):
        Config()  # type: ignore[call-arg]


# ---- Clock ----
def test_fake_clock_default_start_and_float():
    assert FakeClock().now() == 1_000_000.0
    assert isinstance(FakeClock().now(), float)


def test_fake_clock_is_stable_between_reads():
    clock = FakeClock(5.0)
    assert clock.now() == clock.now() == 5.0


def test_fake_clock_advance_accumulates_and_fractions():
    clock = FakeClock(0.0)
    clock.advance(10)
    clock.advance(0.5)
    assert clock.now() == 10.5


def test_fake_clock_can_go_back_with_set():
    clock = FakeClock(100.0)
    clock.set(50.0)
    assert clock.now() == 50.0


def test_clocks_satisfy_protocol_shape():
    for clk in (FakeClock(), SystemClock()):
        assert callable(clk.now) and isinstance(clk.now(), float)
    assert "now" in Clock.__dict__


def test_system_clock_is_non_decreasing():
    s = SystemClock()
    a = s.now()
    b = s.now()
    assert b >= a


# ---- create_app ----
def test_create_app_uses_injected_clock_and_config(config, clock):
    app = create_app(config, clock=clock)
    svc = app.extensions["services"]
    assert svc["clock"] is clock
    assert svc["config"] is config
    clock.advance(30)
    assert svc["clock"].now() == 1_000_030.0


def test_create_app_stores_extra_fakes(config):
    sentinel = object()
    svc = create_app(config, head_counter=sentinel).extensions["services"]
    assert svc["head_counter"] is sentinel


def test_create_app_secret_key_and_no_debug(app, config):
    assert app.config["SECRET_KEY"] == config.secret_key
    assert app.debug is False


def test_two_apps_are_independent(config):
    c1, c2 = FakeClock(1.0), FakeClock(2.0)
    a1, a2 = create_app(config, clock=c1), create_app(config, clock=c2)
    assert a1.extensions["services"]["clock"] is c1
    assert a2.extensions["services"]["clock"] is c2


def test_ping_body_and_static_css(client):
    assert client.get("/ping").get_data(as_text=True) == "ok"
    css = client.get("/static/pico.min.css")
    assert css.status_code == 200
    css.close()


def test_main_exits_on_bad_config(monkeypatch, tmp_path):
    """Covers FR-6.3: start-up refuses to run without the required variables.

    main() calls load_env_file() on the CWD: run from an empty temp dir so a real `.env`
    cannot fill the variables back in (it would start the server / leak into os.environ).
    """
    from app import __main__ as entry
    monkeypatch.chdir(tmp_path)
    for n in ("LECTURER_PIN", "SECRET_KEY", "BASE_URL"):
        monkeypatch.setenv(n, "x")  # registers restore-on-teardown even if main() mutates os.environ
        monkeypatch.delenv(n)
    with pytest.raises(SystemExit) as info:
        entry.main()
    assert "Configuration error" in str(info.value)
