"""F3 polls: service rules and routes (T13)."""
import pytest

from werkzeug.exceptions import NotFound

from app.errors import AlreadyVotedError, InvalidPollError, PollAlreadyOpenError, PollClosedError


@pytest.fixture
def polls(app):
    return app.extensions["services"]["poll_service"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


def phone(app):
    return app.test_client()


@pytest.mark.parametrize("n", [2, 3, 4])
def test_create_accepts_2_to_4_options(polls, n):
    poll = polls.create("Q?", [f"o{i}" for i in range(n)])
    assert [o.label for o in poll.options] == [f"o{i}" for i in range(n)]
    assert poll.is_open and poll.total_votes() == 0


@pytest.mark.parametrize("question,options", [("Q?", ["a"]), ("Q?", ["a", "b", "c", "d", "e"]),
                                              ("  ", ["a", "b"]), ("Q?", ["a", "  "]), ("Q?", [])])
def test_create_rejects_invalid(polls, question, options):
    with pytest.raises(InvalidPollError):
        polls.create(question, options)


def test_second_open_poll_rejected(polls):
    polls.create("Q1", ["a", "b"])
    with pytest.raises(PollAlreadyOpenError):
        polls.create("Q2", ["a", "b"])


def test_new_poll_after_close(polls):
    polls.close(polls.create("Q1", ["a", "b"]).id)
    assert polls.create("Q2", ["a", "b"]).question == "Q2"


def test_vote_counts_and_second_vote_rejected(polls):
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[0].id, "dev1")
    with pytest.raises(AlreadyVotedError):
        polls.vote(poll.id, poll.options[1].id, "dev1")
    polls.vote(poll.id, poll.options[1].id, "dev2")
    assert [o.votes for o in polls.get(poll.id).options] == [1, 1]


def test_vote_after_close_rejected_counts_unchanged(polls):
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[0].id, "dev1")
    polls.close(poll.id)
    with pytest.raises(PollClosedError):
        polls.vote(poll.id, poll.options[0].id, "dev2")
    assert polls.get(poll.id).total_votes() == 1
    assert polls.latest().id == poll.id and polls.current() is None


def test_vote_with_foreign_option_or_unknown_poll(polls):
    first = polls.create("Q1", ["a", "b"])
    polls.close(first.id)
    second = polls.create("Q2", ["c", "d"])
    with pytest.raises(InvalidPollError):
        polls.vote(second.id, first.options[0].id, "dev")
    with pytest.raises(NotFound):
        polls.vote(999, 1, "dev")


def test_student_flow_without_nickname(app, polls):
    poll = polls.create("Pick", ["Yes", "No"])
    p = phone(app)
    assert "Pick" in p.get("/poll").get_data(as_text=True)
    resp = p.post("/poll/vote", data={"poll_id": poll.id, "option_id": poll.options[0].id}, follow_redirects=True)
    assert "your vote is counted" in resp.get_data(as_text=True)
    again = p.post("/poll/vote", data={"poll_id": poll.id, "option_id": poll.options[1].id})
    assert again.status_code == 409 and "You have already voted." in again.get_data(as_text=True)
    assert polls.get(poll.id).total_votes() == 1


def test_student_bad_form_and_no_poll(app):
    p = phone(app)
    assert "No poll is open" in p.get("/poll").get_data(as_text=True)
    assert p.post("/poll/vote", data={"poll_id": "x"}).status_code == 400
    assert p.get("/api/poll/current").get_json() == {"poll": None}


def test_api_current_and_results(app, polls, lecturer):
    poll = polls.create("Q", ["a", "b"])
    polls.vote(poll.id, poll.options[1].id, "dev")
    current = phone(app).get("/api/poll/current").get_json()["poll"]
    assert current["id"] == poll.id and current["open"]
    data = lecturer.get(f"/api/polls/{poll.id}/results").get_json()
    assert data["total"] == 1 and [o["votes"] for o in data["options"]] == [0, 1]
    assert "device" not in str(data) and "dev" not in data


def test_lecturer_routes_need_pin(client, app):
    assert client.get("/lecturer/polls").status_code == 302
    assert client.post("/lecturer/polls", data={"question": "Q", "option": ["a", "b"]}).status_code == 302
    assert client.get("/api/polls/1/results").status_code == 401
    assert app.extensions["services"]["poll_service"].current() is None


def test_lecturer_create_and_close(lecturer, polls):
    resp = lecturer.post("/lecturer/polls", data={"question": "Q", "option": ["a", "b", "", ""]},
                         follow_redirects=True)
    assert "Close poll" in resp.get_data(as_text=True)
    dup = lecturer.post("/lecturer/polls", data={"question": "Q2", "option": ["a", "b"]})
    assert dup.status_code == 409 and "A poll is already open. Close it first." in dup.get_data(as_text=True)
    bad = lecturer.post("/lecturer/polls", data={"question": "", "option": ["a", "b"]})
    assert bad.status_code == 400
    poll = polls.current()
    page = lecturer.post(f"/lecturer/polls/{poll.id}/close", follow_redirects=True).get_data(as_text=True)
    assert "(closed)" in page and polls.current() is None


def test_no_personal_columns(app):
    cols = {r["name"] for t in ("poll", "poll_option", "vote")
            for r in app.extensions["services"]["db"].conn().execute(f"PRAGMA table_info({t})")}
    assert not cols & {"nickname", "ip", "name", "email"}


def test_huge_ids_give_clean_404(lecturer, polls):
    huge = 10**30
    assert lecturer.get(f"/api/polls/{huge}/results").status_code == 404
    p = polls.create("Q", ["a", "b"])
    resp = lecturer.post("/poll/vote", data={"poll_id": huge, "option_id": 1})
    assert resp.status_code == 404
    resp = lecturer.post("/poll/vote", data={"poll_id": p.id, "option_id": huge})
    assert resp.status_code == 400 and polls.get(p.id).total_votes() == 0
