"""F2 comments, extra coverage (T14). Covers FR-2.1-FR-2.4, D9, D21, D29, D31."""
import re
import sqlite3
from pathlib import Path

import pytest

from app import create_app
from app.errors import CommentTooLongError, EmptyCommentError

EMPTY_MSG = b"Please write something before sending."
LONG_MSG = b"Please keep your comment under 500 characters."


@pytest.fixture
def comments(app):
    return app.extensions["services"]["comment_service"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


@pytest.mark.parametrize("char", ["\U0001F600", "א", "é"])
def test_length_counted_in_characters_not_bytes(comments, char):
    """Covers D31: 500 multibyte characters accepted, 501 rejected."""
    comments.post(char * 500)
    with pytest.raises(CommentTooLongError):
        comments.post(char * 501)
    assert len(comments.recent()) == 1


@pytest.mark.parametrize("text", ["", " ", "\n\n", "\t \r\n  ", "  "])
def test_blank_rejected_via_route_with_exact_message(client, comments, text):
    """Covers FR-2.1 error table: exact message, nothing stored."""
    response = client.post("/comments", data={"text": text})
    assert EMPTY_MSG in response.data
    assert response.status_code == 400
    assert comments.recent() == []


def test_missing_field_rejected(client, comments):
    assert EMPTY_MSG in client.post("/comments", data={}).data
    assert comments.recent() == []


def test_too_long_via_route_exact_message_and_not_stored(client, comments):
    response = client.post("/comments", data={"text": "\U0001F600" * 501})
    assert response.status_code == 400 and LONG_MSG in response.data
    assert comments.recent() == []


def test_500_after_trim_accepted(comments):
    """Design: post() strips first, so 500 chars plus padding is accepted."""
    assert len(comments.post("  " + "a" * 500 + "\n").text) == 500


def test_text_is_trimmed_and_inner_newlines_kept(comments):
    """Design (docs/design.md CommentService): post strips the text."""
    assert comments.post("\n  a\nb  \n").text == "a\nb"


def test_post_without_open_session(app, client):
    assert app.extensions["services"]["session_service"].current() is None
    response = client.post("/comments", data={"text": "idea"}, follow_redirects=True)
    assert b"Thanks, sent anonymously." in response.data


def test_redirect_target(client):
    response = client.post("/comments", data={"text": "idea"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/comments?sent=1")


def test_get_page_without_sent_has_no_thanks(client):
    assert b"Thanks, sent anonymously." not in client.get("/comments").data


def test_stored_row_has_only_id_text_created_at(app, comments, clock):
    comments.post("x")
    conn = sqlite3.connect(app.extensions["services"]["config"].database_path)
    cols = [c[1] for c in conn.execute("PRAGMA table_info(comment)")]
    assert cols == ["id", "text", "created_at"]
    assert not any(w in " ".join(cols) for w in ("device", "ip", "nick", "session"))
    assert conn.execute("SELECT * FROM comment").fetchall() == [(1, "x", clock.now())]
    assert not conn.execute("PRAGMA foreign_key_list(comment)").fetchall()


def test_student_post_stores_no_identity(app, client):
    client.post("/comments", data={"text": "anon"}, headers={"X-Forwarded-For": "1.2.3.4"})
    conn = sqlite3.connect(app.extensions["services"]["config"].database_path)
    assert conn.execute("SELECT * FROM comment").fetchall()[0][1] == "anon"
    assert len(conn.execute("SELECT * FROM comment").fetchall()[0]) == 3


def test_same_timestamp_tie_broken_by_id_newest_first(comments, clock):
    for t in ("a", "b", "c"):
        comments.post(t)  # FakeClock not advanced: identical created_at
    assert [c.text for c in comments.recent()] == ["c", "b", "a"]


def test_order_by_time_then_id(comments, clock):
    comments.post("old")
    clock.advance(10)
    comments.post("n1")
    comments.post("n2")
    assert [c.text for c in comments.recent()] == ["n2", "n1", "old"]


def test_persists_after_recreating_app(app, config, comments):
    comments.post("kept")
    again = create_app(config)
    assert [c.text for c in again.extensions["services"]["comment_service"].recent()] == ["kept"]


def test_api_without_pin_is_401_json_and_leaks_nothing(client, comments):
    comments.post("SECRET-TEXT")
    response = client.get("/api/comments")
    assert response.status_code == 401
    assert response.is_json
    assert b"SECRET-TEXT" not in response.data


def test_lecturer_page_without_pin_redirects_and_leaks_nothing(client, comments):
    comments.post("SECRET-TEXT")
    response = client.get("/lecturer/comments")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]
    assert b"SECRET-TEXT" not in response.data


def test_wrong_pin_does_not_grant_access(client, comments):
    comments.post("SECRET-TEXT")
    client.post("/lecturer/login", data={"pin": "0000"})
    assert client.get("/api/comments").status_code == 401


def test_xss_text_not_in_lecturer_page_html_and_js_uses_textcontent(lecturer, comments):
    payload = "<script>alert(1)</script>"
    comments.post(payload)
    page = lecturer.get("/lecturer/comments").data.decode()
    assert payload not in page  # comments are fetched by JS, never inlined
    assert "textContent" in page
    assert not re.search(r"\.innerHTML\s*=|insertAdjacentHTML|document\.write", page)
    assert lecturer.get("/api/comments").get_json()["comments"][0]["text"] == payload


def test_template_static_no_unsafe_sinks():
    for name in ("lecturer_comments.html", "comments.html"):
        src = (Path(__file__).parent.parent / "app" / "templates" / name).read_text()
        assert "|safe" not in src
        assert not re.search(r"\.innerHTML\s*=|insertAdjacentHTML|document\.write", src)
    assert "setInterval(refresh, 2500)" in (
        Path(__file__).parent.parent / "app" / "templates" / "lecturer_comments.html").read_text()


def test_student_confirmation_page_does_not_echo_unescaped_text(client):
    response = client.post("/comments", data={"text": "<b>x</b>" + "y" * 600})
    assert b"<b>x</b>" not in response.data


def test_api_limit_100_newest_kept(lecturer, comments, clock):
    for i in range(105):
        comments.post(f"c{i}")
        clock.advance(1)
    data = lecturer.get("/api/comments").get_json()["comments"]
    assert len(data) == 100
    assert data[0]["text"] == "c104" and data[-1]["text"] == "c5"
    assert all(set(c) == {"text", "created_at"} for c in data)


def test_recent_limit_parameter(comments):
    for i in range(5):
        comments.post(str(i))
    assert [c.text for c in comments.recent(2)] == ["4", "3"]


def test_menu_links_to_poll_and_comments(client):
    html = client.get("/").data.decode()
    assert re.search(r'href="/poll"', html) and re.search(r'href="/comments"', html)


def test_empty_error_type(comments):
    with pytest.raises(EmptyCommentError):
        comments.post(" ")
