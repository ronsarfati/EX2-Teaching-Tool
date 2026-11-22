"""Trivial pytest checks: Flask test client + token module (no personal data, no network)."""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ping_route():
    app = _load("flask_min_app").app
    resp = app.test_client().get("/ping")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_token_fresh_and_expired():
    tok = _load("token_rotation")
    t = tok.make_token("s1:p1", now=1000)
    assert tok.verify_token(t, now=1005) == "s1:p1"
    assert tok.verify_token(t, now=1011) is None


def test_token_many_random_keys():
    """Regression: the binary signature may contain the separator byte; verify 2000 fresh tokens."""
    tok = _load("token_rotation")
    import secrets
    for i in range(2000):
        tok.KEY = secrets.token_bytes(32)
        assert tok.verify_token(tok.make_token(f"s{i}:p{i}", now=1000), now=1001) == f"s{i}:p{i}"
