"""F3 polls, extra coverage (T13).

Covers R6, R14, D4, D9, D21, D28, FR-3.1 to FR-3.4, FR-6.1, FR-6.2, NFR-2.
"""
import re
from pathlib import Path

import pytest

from app.errors import AlreadyVotedError, InvalidPollError, PollAlreadyOpenError, PollClosedError

INVALID_MSG = "A poll needs a question and 2 to 4 options."
OPEN_MSG = "A poll is already open. Close it first."
VOTED_MSG = "You have already voted."
CLOSED_MSG = "This poll is closed."
TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


@pytest.fixture
def polls(app):
    return app.extensions["services"]["poll_service"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def phone(app):
    return app.test_client()


# ---- FR-3.1 option count boundaries and validation ----

@pytest.mark.parametrize("n", [2, 4])
def test_boundary_options_accepted(polls, n):
    """Covers FR-3.1: 2 and 4 options are accepted."""
    assert len(polls.create("Q", [f"o{i}" for i in range(n)]).options) == n


@pytest.mark.parametrize("n", [1, 5])
def test_boundary_options_rejected_exact_message(polls, n):
    """Covers FR-3.1, SRS error table: 1 and 5 options rejected."""
    with pytest.raises(InvalidPollError) as info:
        polls.create("Q", [f"o{i}" for i in range(n)])
    assert info.value.user_message == INVALID_MSG
    assert polls.current() is None


def test_blank_options_stripped_before_counting(polls):
    """Covers FR-3.1: blanks ignored and labels stripped."""
    poll = polls.create("  Q  ", ["  a ", "", "   ", "b"])
    assert poll.question == "Q" and [o.label for o in poll.options] == ["a", "b"]
    with pytest.raises(InvalidPollError):
        polls.create("Q2", ["a", "", "  ", ""])  # only one real option


@pytest.mark.parametrize("question", ["", "   ", "\t\n"])
def test_blank_question_rejected(polls, question):
    """Covers FR-3.1: empty or blank question rejected."""
    with pytest.raises(InvalidPollError) as info:
        polls.create(question, ["a", "b"])
    assert info.value.user_message == INVALID_MSG


def test_invalid_poll_http_message(lecturer):
    """Covers SRS error table: HTTP 400 with exact message."""
    resp = lecturer.post("/lecturer/polls", data={"question": " ", "option": ["a", "b"]})
    assert resp.status_code == 400 and INVALID_MSG in resp.get_data(as_text=True)


# ---- D28 one open poll ----

def test_second_open_poll_rejected_exact_message(polls):
    """Covers D28: second open poll rejected with exact message; first stays."""
    first = polls.create("Q1", ["a", "b"])
    with pytest.raises(PollAlreadyOpenError) as info:
        polls.create("Q2", ["a", "b"])
    assert info.value.user_message == OPEN_MSG
    assert polls.current().id == first.id


def test_unique_index_blocks_second_open_poll_in_db(app):
    """Covers D28: the partial unique index guards at database level."""
    import sqlite3
    conn = app.extensions["services"]["db"].conn()
    conn.execute("INSERT INTO poll(question, created_at) VALUES ('a', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO poll(question, created_at) VALUES ('b', 2)")
    conn.execute("UPDATE poll SET is_open = 0")
    conn.execute("INSERT INTO poll(question, created_at) VALUES ('c', 3)")  # closed ones do not count


def test_close_then_new_poll_allowed(polls):
    """Covers FR-3.4, D28."""
    first = polls.create("Q1", ["a", "b"])
    closed = polls.close(first.id)
    assert not closed.is_open
    second = polls.create("Q2", ["c", "d"])
    assert second.is_open and second.id != first.id and polls.current().id == second.id
    assert polls.close(second.id).is_open is False
    assert polls.close(second.id).is_open is False  # closing twice is harmless


# ---- FR-3.2 one vote per device ----

def test_one_vote_per_device_count_unchanged(polls):
    """Covers FR-3.2: second vote (even for another option) rejected, count unchanged."""
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[0].id, "devA")
    for option in poll.options:
        with pytest.raises(AlreadyVotedError) as info:
            polls.vote(poll.id, option.id, "devA")
        assert info.value.user_message == VOTED_MSG
    assert [o.votes for o in polls.get(poll.id).options] == [1, 0]


def test_different_devices_all_counted(polls):
    """Covers FR-3.2, FR-3.3."""
    poll = polls.create("Q", ["a", "b", "c"])
    for i, token in enumerate(["d1", "d2", "d3", "d4", "d5"]):
        polls.vote(poll.id, poll.options[0 if i < 3 else 2].id, token)
    assert [o.votes for o in polls.get(poll.id).options] == [3, 0, 2]


def test_same_device_can_vote_in_next_poll(polls):
    """Covers FR-3.2: the PK is (poll_id, device_token), so a new poll allows a new vote."""
    first = polls.create("Q1", ["a", "b"])
    polls.vote(first.id, first.options[0].id, "dev")
    polls.close(first.id)
    second = polls.create("Q2", ["a", "b"])
    polls.vote(second.id, second.options[1].id, "dev")
    assert polls.get(second.id).total_votes() == 1 and polls.get(first.id).total_votes() == 1


def test_vote_after_close_rejected_counts_unchanged_exact_message(polls):
    """Covers FR-3.4."""
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[0].id, "d1")
    polls.close(poll.id)
    with pytest.raises(PollClosedError) as info:
        polls.vote(poll.id, poll.options[1].id, "d2")
    assert info.value.user_message == CLOSED_MSG
    assert [o.votes for o in polls.get(poll.id).options] == [1, 0]


def test_vote_after_close_http(app, polls):
    """Covers FR-3.4 over HTTP: 409 and message, counts unchanged."""
    poll = polls.create("Q", ["a", "b"])
    polls.close(poll.id)
    resp = phone(app).post("/poll/vote", data={"poll_id": poll.id, "option_id": poll.options[0].id})
    assert resp.status_code == 409 and CLOSED_MSG in resp.get_data(as_text=True)
    assert polls.get(poll.id).total_votes() == 0


def test_second_vote_http_message(app, polls):
    """Covers FR-3.2 over HTTP."""
    poll = polls.create("Q", ["a", "b"])
    p = phone(app)
    data = {"poll_id": poll.id, "option_id": poll.options[0].id}
    assert p.post("/poll/vote", data=data).status_code == 302
    resp = p.post("/poll/vote", data=data)
    assert resp.status_code == 409 and VOTED_MSG in resp.get_data(as_text=True)
    assert polls.get(poll.id).total_votes() == 1


def test_two_phones_two_votes(app, polls):
    """Covers FR-3.2: distinct device cookies count separately."""
    poll = polls.create("Q", ["a", "b"])
    for _ in range(2):
        phone(app).post("/poll/vote", data={"poll_id": poll.id, "option_id": poll.options[0].id})
    assert polls.get(poll.id).total_votes() == 2


# ---- forged ids ----

@pytest.mark.parametrize("form", [
    {"poll_id": "999", "option_id": "1"},
    {"poll_id": "abc", "option_id": "1"},
    {"poll_id": "1"},
    {"option_id": "1"},
    {"poll_id": "", "option_id": ""},
    {"poll_id": "-1", "option_id": "-1"},
    {"poll_id": "99999999999999999999999", "option_id": "1"},
])
def test_forged_form_clean_4xx(app, polls, form):
    """Covers D28 robustness: forged ids give a 4xx page, never a traceback or a vote."""
    polls.create("Q", ["a", "b"])
    resp = phone(app).post("/poll/vote", data=form)
    assert 400 <= resp.status_code < 500
    assert "Traceback" not in resp.get_data(as_text=True)
    assert polls.current().total_votes() == 0


def test_option_of_another_poll_rejected(app, polls):
    """Covers D28: option id of another poll refused with 400, no vote stored."""
    first = polls.create("Q1", ["a", "b"])
    polls.close(first.id)
    second = polls.create("Q2", ["c", "d"])
    resp = phone(app).post("/poll/vote", data={"poll_id": second.id, "option_id": first.options[0].id})
    assert resp.status_code == 400 and INVALID_MSG in resp.get_data(as_text=True)
    assert polls.get(second.id).total_votes() == 0 and polls.get(first.id).total_votes() == 0


def test_results_of_unknown_poll_is_404(lecturer):
    """Covers robustness: unknown id on the results API."""
    assert lecturer.get("/api/polls/999/results").status_code == 404


def test_close_unknown_poll_is_404(lecturer):
    assert lecturer.post("/lecturer/polls/999/close").status_code == 404


# ---- results JSON ----

def test_results_json_sum_equals_votes(app, polls, lecturer):
    """Covers FR-3.3: per-option counts sum to total and to number of votes cast."""
    poll = polls.create("Q", ["a", "b", "c"])
    picks = [0, 0, 1, 2, 2, 2, 1]
    for i, k in enumerate(picks):
        polls.vote(poll.id, poll.options[k].id, f"dev{i}")
    data = lecturer.get(f"/api/polls/{poll.id}/results").get_json()
    assert [o["votes"] for o in data["options"]] == [2, 2, 3]
    assert sum(o["votes"] for o in data["options"]) == data["total"] == len(picks)
    assert data["open"] is True and data["question"] == "Q"


def test_results_stay_visible_after_close(polls, lecturer):
    """Covers FR-3.4."""
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[0].id, "d")
    polls.close(poll.id)
    data = lecturer.get(f"/api/polls/{poll.id}/results").get_json()
    assert data["open"] is False and data["total"] == 1
    page = lecturer.get("/lecturer/polls").get_data(as_text=True)
    assert "(closed)" in page and "Q" in page


def test_current_api_open_closed(app, polls):
    """Covers FR-3.2: current poll JSON is null once closed."""
    poll = polls.create("Q", ["a", "b"])
    assert phone(app).get("/api/poll/current").get_json()["poll"]["id"] == poll.id
    polls.close(poll.id)
    assert phone(app).get("/api/poll/current").get_json() == {"poll": None}


# ---- access control ----

def test_lecturer_routes_require_pin(client, polls):
    """Covers FR-6.1: all lecturer poll endpoints refuse an anonymous browser."""
    poll = polls.create("Q", ["a", "b"])
    assert client.get("/lecturer/polls").status_code == 302
    assert client.post("/lecturer/polls", data={"question": "X", "option": ["a", "b"]}).status_code == 302
    assert client.post(f"/lecturer/polls/{poll.id}/close").status_code == 302
    assert client.get(f"/api/polls/{poll.id}/results").status_code == 401
    assert polls.current().id == poll.id and polls.current().question == "Q"


def test_student_needs_no_pin_no_nickname(app, polls):
    """Covers FR-3.2, FR-6.2: a fresh browser sees the poll and votes."""
    poll = polls.create("Q", ["a", "b"])
    p = phone(app)
    assert p.get("/poll").status_code == 200
    assert p.get("/api/poll/current").status_code == 200
    resp = p.post("/poll/vote", data={"poll_id": poll.id, "option_id": poll.options[1].id})
    assert resp.status_code == 302
    assert polls.get(poll.id).total_votes() == 1


# ---- privacy ----

def test_no_personal_columns_in_poll_tables(app):
    """Covers D21, D28: no nickname/ip/name/email columns; vote stores a device token only."""
    conn = app.extensions["services"]["db"].conn()
    cols = {t: {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")} for t in ("poll", "poll_option", "vote")}
    for names in cols.values():
        assert not any(bad in n.lower() for n in names for bad in ("nickname", "ip", "name", "email", "address"))
    assert "device_token" in cols["vote"]


# ---- escaping ----

XSS = '<script>alert(1)</script>"&'


def test_student_page_escapes_text(app, polls):
    """Covers HTML escaping on poll.html."""
    polls.create(XSS, [XSS + "1", "<img src=x onerror=alert(2)>"])
    html = phone(app).get("/poll").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_lecturer_page_escapes_text(polls, lecturer):
    """Covers HTML escaping on lecturer_poll.html."""
    polls.create(XSS, [XSS + "1", "<img src=x onerror=alert(2)>"])
    html = lecturer.get("/lecturer/polls").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_js_uses_textcontent_not_innerhtml():
    """Covers static check: dynamic labels are inserted as text."""
    lect = (TEMPLATES / "lecturer_poll.html").read_text()
    stud = (TEMPLATES / "poll.html").read_text()
    for src in (lect, stud):
        assert "innerHTML" not in src and "insertAdjacentHTML" not in src and "document.write" not in src
    assert "textContent" in lect or ".append(" in lect
    assert "textContent" in lect


# ---- polling interval (D4, NFR-2) ----

def test_polling_intervals_2_to_3_seconds():
    """Covers D4, NFR-2: setInterval periods between 2000 and 3000 ms."""
    for name in ("poll.html", "lecturer_poll.html"):
        src = (TEMPLATES / name).read_text()
        periods = [int(m) for m in re.findall(r"setInterval\([\s\S]*?\},\s*(\d+)\s*\)", src)]
        assert periods, name
        assert all(2000 <= p <= 3000 for p in periods), (name, periods)
