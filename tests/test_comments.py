"""F2 comments: service rules, anonymity, routes (T14)."""
import sqlite3

import pytest

from app import create_app
from app.errors import CommentTooLongError, EmptyCommentError


@pytest.fixture
def comments(app):
    return app.extensions["services"]["comment_service"]


@pytest.fixture
def lecturer(client):
    client.post("/lecturer/login", data={"pin": "1234"})
    return client


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_blank_rejected(comments, text):
    with pytest.raises(EmptyCommentError):
        comments.post(text)
    assert comments.recent() == []


def test_length_limit(comments):
    comments.post("x" * 500)
    with pytest.raises(CommentTooLongError):
        comments.post("x" * 501)
    assert len(comments.recent()) == 1


def test_posted_without_open_session_and_only_text_and_time_stored(app, comments, clock):
    assert app.extensions["services"]["session_service"].current() is None
    comments.post("  more examples  ")
    conn = sqlite3.connect(app.extensions["services"]["config"].database_path)
    assert [c[1] for c in conn.execute("PRAGMA table_info(comment)")] == ["id", "text", "created_at"]
    assert conn.execute("SELECT text, created_at FROM comment").fetchall() == [("more examples", clock.now())]


def test_newest_first(comments, clock):
    comments.post("first")
    clock.advance(5)
    comments.post("second")
    assert [c.text for c in comments.recent()] == ["second", "first"]


def test_survives_new_app_on_same_db(app, config, comments):
    comments.post("kept")
    again = create_app(config)
    assert [c.text for c in again.extensions["services"]["comment_service"].recent()] == ["kept"]


def test_student_post_shows_thanks(client):
    response = client.post("/comments", data={"text": "hi"}, follow_redirects=True)
    assert b"Thanks, sent anonymously." in response.data


def test_student_errors_show_messages(client):
    assert b"Please write something before sending." in client.post("/comments", data={"text": " "}).data
    too_long = client.post("/comments", data={"text": "x" * 501})
    assert too_long.status_code == 400
    assert b"Please keep your comment under 500 characters." in too_long.data


def test_lecturer_pages_need_pin(client):
    assert client.get("/lecturer/comments").status_code in (302, 401, 403)
    assert client.get("/api/comments").status_code in (302, 401, 403)


def test_api_lists_newest_first_without_identity(app, lecturer, comments):
    comments.post("<b>one</b>")
    comments.post("two")
    data = lecturer.get("/api/comments").get_json()
    assert [c["text"] for c in data["comments"]] == ["two", "<b>one</b>"]
    assert set(data["comments"][0]) == {"text", "created_at"}
    assert lecturer.get("/lecturer/comments").status_code == 200


def test_student_page_escapes_and_links_exist(client, lecturer):
    assert b'href="/poll"' in client.get("/").data and b'href="/comments"' in client.get("/").data
    assert b"/lecturer/comments" in lecturer.get("/lecturer").data
    assert b"textContent" in lecturer.get("/lecturer/comments").data
