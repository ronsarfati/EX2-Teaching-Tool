"""T17: homework review with anonymised comparison and the lecturer's peer list. Fakes only: no network, no key."""
import pytest

from app import create_app
from app.adapters.repo_fetcher import RepoExtract
from app.errors import LLMUnavailableError
from app.services.homework import NO_PEER_SENTENCE
from tests.fakes import FakeLLMClient, FakeRepoFetcher

TARGET = "https://github.com/student-a-example/target-repo"
PEER_B = "https://github.com/peer-b-example/secret-project"
PEER_C = "https://github.com/peer-c-example/other-work"


def extract(text="print('hi')", files=3, lines=42):
    return RepoExtract(text, files, lines, False)


@pytest.fixture
def repos():
    return {
        TARGET: extract(files=3, lines=42),
        PEER_B: extract("# secret-project by peer-b-example\nx = 1", files=7, lines=111),
        PEER_C: extract("peer-c-example wrote other-work", files=5, lines=222),
    }


@pytest.fixture
def llm():
    return FakeLLMClient(reply="Good. Compared with Submission B and peer-b-example/secret-project, see peer-c-example.")


@pytest.fixture
def fetcher(repos):
    return FakeRepoFetcher(repos)


@pytest.fixture
def app(config, clock, llm, fetcher):
    return create_app(config, clock=clock, llm=llm, fetcher=fetcher)


@pytest.fixture
def reviewer(app):
    return app.extensions["services"]["reviewer"]


def login(client):
    assert client.post("/lecturer/login", data={"pin": "1234"}).status_code == 302


def test_prompt_labels_metrics_and_masks_peer_names(reviewer, llm):
    reviewer.set_peer_repos([PEER_B, PEER_C])
    result = reviewer.review(TARGET)
    call = llm.calls[0]
    for label in ("Submission A", "Submission B", "Submission C"):
        assert label in call["prompt"]
    assert "7 files, 111 lines" in call["prompt"]
    for secret in ("peer-b-example", "secret-project", "peer-c-example", "other-work", "github.com/peer-b-example"):
        assert secret not in call["prompt"]
        assert secret not in result.review_text
    assert result.comparison_available
    assert set(result.peer_metrics) == {"Submission B", "Submission C"}


def test_target_excluded_from_peers_and_only_two_used(reviewer, fetcher):
    reviewer.set_peer_repos([TARGET + "/", PEER_B, PEER_C, "https://github.com/peer-d-example/third"])
    reviewer.review(TARGET)
    fetched = [url for url, _ in fetcher.calls]
    assert fetched == [TARGET, PEER_B, PEER_C]


def test_failed_peer_is_skipped(reviewer, repos, llm):
    reviewer.set_peer_repos(["https://github.com/ghost/missing", PEER_C])
    result = reviewer.review(TARGET)
    assert list(result.peer_metrics) == ["Submission B"]
    assert "other-work" not in llm.calls[0]["prompt"]


def test_no_peer_still_reviews(reviewer, llm):
    result = reviewer.review(TARGET)
    assert not result.comparison_available
    assert result.review_text.startswith("Good")


def test_invalid_and_missing_target(client):
    assert client.post("/review", data={"url": "https://example.com/x/y"}).status_code == 400
    response = client.post("/review", data={"url": "https://github.com/nobody/nothing"})
    assert response.status_code == 400
    assert b"Is it public?" in response.data


def test_llm_failure_message(config, clock, fetcher):
    app = create_app(config, clock=clock, fetcher=fetcher, llm=FakeLLMClient(error=LLMUnavailableError("review")))
    response = app.test_client().post("/review", data={"url": TARGET})
    assert response.status_code == 503
    assert b"The review service is unavailable right now. Please try again later." in response.data


def test_default_client_without_key_is_unavailable(config, clock, fetcher):
    app = create_app(config, clock=clock, fetcher=fetcher)  # real ClaudeClient, no key: no network call
    assert app.test_client().post("/review", data={"url": TARGET}).status_code == 503


def test_review_page_needs_no_pin_and_shows_metrics(client):
    assert client.get("/review").status_code == 200
    response = client.post("/review", data={"url": TARGET})
    assert response.status_code == 200
    assert NO_PEER_SENTENCE.encode() in response.data
    assert b"3 files, 42 lines" in response.data


def test_review_output_is_escaped(config, clock, fetcher):
    app = create_app(config, clock=clock, fetcher=fetcher, llm=FakeLLMClient(reply="<script>alert(1)</script>"))
    response = app.test_client().post("/review", data={"url": TARGET})
    assert b"<script>alert(1)" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_nothing_stored_but_peer_list(app, client):
    client.post("/review", data={"url": TARGET})
    conn = app.extensions["services"]["db"].conn()
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    rows = sum(conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in tables)
    assert rows == 0


def test_peers_page_needs_pin(client):
    assert client.get("/lecturer/peers").status_code == 302
    assert client.post("/lecturer/peers", data={"urls": PEER_B}).status_code == 302


def test_peers_save_and_used_by_next_review(client, llm):
    login(client)
    response = client.post("/lecturer/peers", data={"urls": f"{PEER_B}\n\n{PEER_C}.git\n"})
    assert response.status_code == 302
    assert PEER_B.encode() in client.get("/lecturer/peers").data
    client.post("/review", data={"url": TARGET})
    assert "Submission C" in llm.calls[0]["prompt"]


def test_peers_invalid_line_keeps_list(client, reviewer):
    login(client)
    client.post("/lecturer/peers", data={"urls": PEER_B})
    response = client.post("/lecturer/peers", data={"urls": "not a url"})
    assert response.status_code == 400
    assert b"public GitHub repository link" in response.data
    assert reviewer.peer_repos() == [PEER_B]
