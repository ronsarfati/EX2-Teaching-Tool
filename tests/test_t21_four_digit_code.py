"""T21 (D33): the projected code has exactly 4 ASCII digits, zero-padded. FakeClock only."""
import pytest

from app.services.credentials import RotatingCredentials
from tests.fakes import FakeClock

T0 = 1_700_000_000.0


@pytest.fixture
def clock():
    return FakeClock(T0)


@pytest.fixture
def creds(clock):
    return RotatingCredentials("test-secret", clock)


def test_code_digits_constant():
    assert RotatingCredentials.CODE_DIGITS == 4


def test_leading_zeros_are_kept(creds, clock):
    """About 10% of the codes start with 0; they must stay 4 characters long and valid."""
    codes = []
    for i in range(500):
        clock.set(T0 + 5 * i)
        codes.append(creds.current_code(1))
    zero_led = [c for c in codes if c.startswith("0")]
    assert zero_led and all(len(c) == 4 for c in codes)
    clock.set(T0)
    assert creds.is_valid_code(1, creds.current_code(1))


@pytest.mark.parametrize("builder", [
    lambda c: c[1:],          # 3 digits
    lambda c: "0" + c,        # 5 digits
    lambda c: " " + c,        # leading space
    lambda c: c[:2] + " " + c[2:],
    lambda c: "+" + c[1:],    # sign instead of a digit
    lambda c: "".join(chr(ord(d) + 0xFF10 - 0x30) for d in c),  # full-width digits
    lambda c: "",
])
def test_malformed_input_refused(creds, builder):
    assert not creds.is_valid_code(1, builder(creds.current_code(1)))


def test_arabic_indic_digits_refused(creds):
    assert not creds.is_valid_code(1, "١٢٣٤")


# ---- T21 additions (tester) -------------------------------------------------------------------

def test_always_four_ascii_digits_and_full_range(creds, clock):
    """Covers T21-1: many slices; leading zeros appear; values span 0000-9999 plausibly."""
    values = []
    for i in range(4000):
        clock.set(T0 + 5 * i)
        code = creds.current_code(1)
        assert len(code) == 4 and code.isascii() and code.isdigit()
        values.append(int(code))
    assert any(v < 1000 for v in values) and any(v >= 9000 for v in values)
    assert min(values) < 100 and max(values) > 9900
    for decile in range(10):  # roughly uniform: each thousand-block hit 300-500 times out of 4000
        n = sum(1 for v in values if v // 1000 == decile)
        assert 250 < n < 550


def test_rotation_inside_and_at_boundary(creds, clock):
    """Covers T21-2."""
    start = T0 - T0 % 5  # slice start
    clock.set(start)
    first = creds.current_code(1)
    clock.set(start + 4.999)
    assert creds.current_code(1) == first
    clock.set(start + 5)
    changes = 0
    for i in range(200):
        clock.set(start + 5 * i)
        a = creds.current_code(1)
        clock.set(start + 5 * i + 5)
        changes += a != creds.current_code(1)
    assert changes >= 195


def test_p1_current_and_previous_accepted_older_refused(creds, clock):
    """Covers T21-3."""
    start = T0 - T0 % 5
    clock.set(start)
    older = creds.current_code(1)
    clock.set(start + 5)
    previous = creds.current_code(1)
    clock.set(start + 10)
    current = creds.current_code(1)
    assert creds.is_valid_code(1, current) and creds.is_valid_code(1, previous)
    if older not in (current, previous):
        assert not creds.is_valid_code(1, older)
    clock.set(start + 15)
    if previous != creds.current_code(1) and previous != current:
        assert not creds.is_valid_code(1, previous) or previous == creds.current_code(1)


def test_non_str_and_odd_inputs_never_raise(creds):
    for bad in (None, 1234, b"1234", ["1", "2", "3", "4"], "1234\n", "1234\x00", "12​34"):
        assert creds.is_valid_code(1, bad) is False


def test_other_session_code_not_valid(creds):
    assert not creds.is_valid_code(2, creds.current_code(1)) or creds.current_code(1) == creds.current_code(2)


def test_brute_force_figure_documented():
    """Covers T21-8: 2 / 10,000 per random guess (current + previous), i.e. 5,000 expected guesses."""
    assert 2 / 10 ** RotatingCredentials.CODE_DIGITS == 0.0002
    assert 10 ** RotatingCredentials.CODE_DIGITS / 2 == 5000


# --- through the web layer ---

def _phone(app):
    c = app.test_client()
    state = app.extensions["services"]["session_service"].projector_state()
    c.get(state.check_in_url.split("test.example")[1])
    return c, state


def _attempts(app):
    from sqlite3 import connect
    conn = connect(app.extensions["services"]["config"].database_path)
    row = conn.execute("SELECT attempts FROM checkin_window").fetchone()
    conn.close()
    return row[0] if row else None


def test_projector_json_and_page_show_four_digits(app, client):
    client.post("/lecturer/login", data={"pin": "1234"})
    assert client.get("/api/projector").get_json()["code"] is None
    app.extensions["services"]["session_service"].open_session()
    code = client.get("/api/projector").get_json()["code"]
    assert len(code) == 4 and code.isdigit()
    page = client.get("/lecturer/projector").get_data(as_text=True)
    assert "3-digit" not in page and "3 digit" not in page


def test_student_input_attributes(app):
    app.extensions["services"]["session_service"].open_session()
    c, _ = _phone(app)
    c2 = app.test_client()
    html = c2.get(app.extensions["services"]["session_service"].projector_state().check_in_url
                  .split("test.example")[1]).get_data(as_text=True)
    assert 'maxlength="4"' in html and 'pattern="[0-9]{4}"' in html and 'inputmode="numeric"' in html
    assert "4-digit code" in html and "3-digit" not in html


def test_no_three_digit_wording_in_app():
    from pathlib import Path
    for p in (Path(__file__).resolve().parent.parent / "app").rglob("*"):
        if p.is_file() and p.suffix in {".py", ".html", ".js"}:
            text = p.read_text(encoding="utf-8").lower()
            assert "3-digit" not in text and "three-digit" not in text and "3 digit" not in text, p


def _malformed(code):
    return [code[1:], "0" + code, "+" + code[1:], "-" + code[1:], code[:2] + " " + code[2:], "".join(chr(ord(d) + 0xFF10 - 0x30) for d in code),
            "".join(chr(ord(d) + 0x0660 - 0x30) for d in code), "", "abcd", "12.4", "1e03"]


def test_malformed_codes_via_post_refused_and_counted(app):
    """Covers T21-4: every malformed submission = wrong code and one attempt (P2)."""
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    bad = _malformed(state.code)
    count = 0
    for value in bad[:5]:
        r = c.post("/checkin", data={"nickname": "Fox", "code": value})
        assert r.status_code == 400 and b"Wrong code. Type the code shown under the QR now." in r.data, value
        count += 1
        assert _attempts(app) == count
    # the 6th attempt is refused even with the right code
    r = c.post("/checkin", data={"nickname": "Fox", "code": state.code})
    assert r.status_code == 429 and b"Too many tries. Scan the QR code again." in r.data


@pytest.mark.parametrize("index", range(11))
def test_each_malformed_shape_via_post(app, index):
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    value = _malformed(state.code)[index]
    r = c.post("/checkin", data={"nickname": "Fox", "code": value})
    assert r.status_code == 400 and b"Wrong code" in r.data, repr(value)
    assert _attempts(app) == 1


@pytest.mark.parametrize("pad", [" {c}", "{c} ", "  {c}\t", "{c}\n"])
def test_outer_whitespace_is_stripped_by_route_and_accepted(app, pad):
    """Covers T21-4 (updated): the route strips outer whitespace (usability); is_valid_code stays strict."""
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    r = c.post("/checkin", data={"nickname": "Fox", "code": pad.format(c=state.code)})
    assert r.status_code == 200 and b"You are checked in" in r.data


def test_inner_space_refused_and_counted(app):
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    r = c.post("/checkin", data={"nickname": "Fox", "code": state.code[:2] + " " + state.code[2:]})
    assert r.status_code == 400 and b"Wrong code" in r.data and _attempts(app) == 1


def test_five_attempts_then_sixth_rejected_new_scan_resets(app):
    """Covers T21-5, OI-7."""
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    wrong = f"{(int(state.code) + 7) % 10000:04d}"
    for i in range(5):
        assert c.post("/checkin", data={"nickname": "Fox", "code": wrong}).status_code == 400
    assert c.post("/checkin", data={"nickname": "Fox", "code": state.code}).status_code == 429
    # new scan: attempts restart
    state = app.extensions["services"]["session_service"].projector_state()
    c.get(state.check_in_url.split("test.example")[1])
    assert _attempts(app) == 0
    assert c.post("/checkin", data={"nickname": "Fox", "code": state.code}).status_code == 200


def test_previous_slice_code_accepted_via_post_older_refused(app, clock):
    app.extensions["services"]["session_service"].open_session()
    c, state = _phone(app)
    old = state.code
    clock.advance(5)
    for_prev = app.extensions["services"]["session_service"].projector_state().code
    r = c.post("/checkin", data={"nickname": "Fox", "code": old})
    assert r.status_code == 200  # previous slice
    c2, _ = _phone(app)
    clock.advance(5)  # old is now two slices back
    cur = app.extensions["services"]["session_service"].projector_state().code
    if old not in (cur, for_prev):
        assert c2.post("/checkin", data={"nickname": "Cat", "code": old}).status_code == 400
