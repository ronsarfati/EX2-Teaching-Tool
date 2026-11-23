"""T17 extra: masking edge cases, peer selection, errors, no storage, auth. Fakes only: no network, no key.

Covers FR-5.1-FR-5.5, D11, D12, D21, D23, D31 (OI-9).
"""
import pytest

from app import create_app
from app.adapters.repo_fetcher import RepoExtract
from app.errors import LLMUnavailableError
from tests.fakes import FakeLLMClient, FakeRepoFetcher

TARGET = "https://github.com/student-a-example/target-repo"
PEER_B = "https://github.com/peer-b-example/secret-project"
PEER_C = "https://github.com/peer-c-example/other-work"


def ex(text="code", files=1, lines=2):
    return RepoExtract(text, files, lines, False)


class RecordingLLM(FakeLLMClient):
    """FakeLLMClient that also records the `feature` argument."""

    def complete(self, system, prompt, max_tokens, feature="review"):
        self.calls.append({"system": system, "prompt": prompt, "max_tokens": max_tokens, "feature": feature})
        return self.reply(prompt) if callable(self.reply) else self.reply


def make(config, clock, repos, reply="OK", llm=None):
    llm = llm or RecordingLLM(reply=reply)
    fetcher = FakeRepoFetcher(repos)
    app = create_app(config, clock=clock, llm=llm, fetcher=fetcher)
    return app, llm, fetcher, app.extensions["services"]["reviewer"]


def tables_snapshot(app):
    conn = app.extensions["services"]["db"].conn()
    names = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {n: [tuple(r) for r in conn.execute(f"SELECT * FROM {n}")] for n in names}


def login(client):
    assert client.post("/lecturer/login", data={"pin": "1234"}).status_code == 302


# ---- masking ----

def test_masks_mixed_case_in_prompt_and_output(config, clock):
    """Covers FR-5.4, D11."""
    repos = {TARGET: ex(), PEER_B: ex("Peer-B-Example and SECRET-Project and PEER-B-EXAMPLE/Secret-project")}
    _, llm, _, rv = make(config, clock, repos, reply="see PEER-B-EXAMPLE, SeCrEt-PrOjEcT")
    rv.set_peer_repos([PEER_B])
    result = rv.review(TARGET)
    p = llm.calls[0]["prompt"].lower()
    assert "peer-b-example" not in p and "secret-project" not in p
    assert "peer-b-example" not in result.review_text.lower()
    assert "secret-project" not in result.review_text.lower()
    assert result.review_text == "see Submission B, Submission B"


def test_masks_full_url_and_git_url(config, clock):
    """Covers FR-5.4: full URL, .git URL and trailing slash variants."""
    text = ("https://github.com/peer-b-example/secret-project\n"
            "HTTPS://GITHUB.COM/Peer-B-Example/Secret-Project\n"
            "https://github.com/peer-b-example/secret-project.git\n"
            "https://github.com/peer-b-example/secret-project/\n")
    _, llm, _, rv = make(config, clock, {TARGET: ex(), PEER_B: ex(text)},
                         reply="clone https://github.com/peer-b-example/secret-project.git now")
    rv.set_peer_repos([PEER_B + ".git"])
    result = rv.review(TARGET)
    for bad in ("peer-b-example", "secret-project", "github.com/peer-b"):
        assert bad not in llm.calls[0]["prompt"].lower()
        assert bad not in result.review_text.lower()
    assert "Submission B" in result.review_text


def test_peer_name_inside_other_peer_text_is_masked(config, clock):
    """Covers FR-5.4: peer C's name quoted in peer B's README is masked with C's label."""
    repos = {TARGET: ex(), PEER_B: ex("forked from peer-c-example/other-work"), PEER_C: ex("plain")}
    _, llm, _, rv = make(config, clock, repos)
    rv.set_peer_repos([PEER_B, PEER_C])
    rv.review(TARGET)
    prompt = llm.calls[0]["prompt"]
    assert "peer-c-example" not in prompt and "other-work" not in prompt
    assert "forked from Submission C/Submission C" in prompt


def test_only_whole_tokens_masked(config, clock):
    """Covers FR-5.4: owner 'art' is not masked inside 'smart' or 'party'."""
    peer = "https://github.com/art/zzproj"
    repos = {TARGET: ex(), peer: ex("smart party art. Art!")}
    _, llm, _, rv = make(config, clock, repos, reply="smart party, art wins")
    rv.set_peer_repos([peer])
    result = rv.review(TARGET)
    assert "smart party Submission B. Submission B!" in llm.calls[0]["prompt"]
    assert result.review_text == "smart party, Submission B wins"


def test_target_name_not_masked(config, clock):
    """Covers FR-5.4: only peers are anonymised, the target's own text is untouched."""
    repos = {TARGET: ex("student-a-example wrote target-repo"), PEER_B: ex()}
    _, llm, _, rv = make(config, clock, repos)
    rv.set_peer_repos([PEER_B])
    rv.review(TARGET)
    assert "student-a-example wrote target-repo" in llm.calls[0]["prompt"]


# ---- peer selection ----

@pytest.mark.parametrize("variant", [TARGET + ".git", TARGET + "/", TARGET.upper().replace("HTTPS", "https"),
                                     "https://github.com/STUDENT-A-example/Target-Repo"])
def test_target_variants_excluded_from_peers(config, clock, variant):
    """Covers FR-5.2 (target never its own peer)."""
    _, llm, fetcher, rv = make(config, clock, {TARGET: ex(), PEER_B: ex()})
    rv.set_peer_repos([variant, PEER_B])
    result = rv.review(TARGET)
    assert [u for u, _ in fetcher.calls] == [TARGET, PEER_B]
    assert list(result.peer_metrics) == ["Submission B"]


def test_empty_peer_list_reviews_alone(config, clock):
    """Covers FR-5.2: no peers -> target alone, comparison_available False."""
    _, llm, _, rv = make(config, clock, {TARGET: ex()})
    result = rv.review(TARGET)
    assert not result.comparison_available and result.peer_metrics == {}
    assert "Submission B" not in llm.calls[0]["prompt"]


def test_duplicate_peers_collapsed(config, clock):
    """Covers FR-5.5: duplicates (also .git / case variants) are stored once, so only one comparison."""
    _, llm, fetcher, rv = make(config, clock, {TARGET: ex(), PEER_B: ex()})
    rv.set_peer_repos([PEER_B, PEER_B, PEER_B + ".git"])
    assert rv.peer_repos() == [PEER_B]
    result = rv.review(TARGET)
    assert list(result.peer_metrics) == ["Submission B"]
    assert len(fetcher.calls) == 2  # target + 1 peer


def test_more_than_two_peers_only_first_two(config, clock):
    """Covers FR-5.2 boundary: 3 listed -> 2 used."""
    third = "https://github.com/peer-d-example/third"
    repos = {TARGET: ex(), PEER_B: ex(), PEER_C: ex(), third: ex()}
    _, llm, fetcher, rv = make(config, clock, repos)
    rv.set_peer_repos([PEER_B, PEER_C, third])
    rv.review(TARGET)
    assert third not in [u for u, _ in fetcher.calls]
    assert "Submission D" not in llm.calls[0]["prompt"]


def test_all_peers_failing_reviews_target_alone(config, clock):
    """Covers FR-5.2/5.3: unreachable peers skipped, review still produced."""
    _, llm, _, rv = make(config, clock, {TARGET: ex()})
    rv.set_peer_repos([PEER_B, PEER_C])
    result = rv.review(TARGET)
    assert not result.comparison_available
    assert result.review_text == "OK"


def test_first_peer_failing_second_labelled_b(config, clock):
    """Covers FR-5.2: labels follow the peers actually fetched."""
    _, llm, _, rv = make(config, clock, {TARGET: ex(), PEER_C: ex("x")})
    rv.set_peer_repos([PEER_B, PEER_C])
    assert list(rv.review(TARGET).peer_metrics) == ["Submission B"]


# ---- prompt ----

def test_prompt_metrics_and_feature(config, clock):
    """Covers FR-5.1/5.3: metrics in prompt, feature='review', bounded tokens."""
    repos = {TARGET: ex(files=3, lines=42), PEER_B: ex(files=7, lines=111)}
    _, llm, _, rv = make(config, clock, repos)
    rv.set_peer_repos([PEER_B])
    rv.review(TARGET)
    call = llm.calls[0]
    assert call["feature"] == "review"
    assert call["max_tokens"] == rv.MAX_TOKENS
    assert "Metrics: 3 files, 42 lines" in call["prompt"]
    assert "Metrics: 7 files, 111 lines" in call["prompt"]
    assert "Submission A" in call["prompt"]


def test_truncation_noted_in_prompt(config, clock):
    """Covers FR-5.3: truncated extract is flagged."""
    _, llm, _, rv = make(config, clock, {TARGET: RepoExtract("x", 1, 1, True)})
    rv.review(TARGET)
    assert "(text truncated)" in llm.calls[0]["prompt"]


def test_fetch_caps(config, clock):
    """Covers FR-5.3: target and peer size caps passed to fetcher."""
    _, _, fetcher, rv = make(config, clock, {TARGET: ex(), PEER_B: ex()})
    rv.set_peer_repos([PEER_B])
    rv.review(TARGET)
    assert fetcher.calls == [(TARGET, rv.TARGET_CAP_CHARS), (PEER_B, rv.PEER_CAP_CHARS)]


# ---- errors ----

def test_invalid_target_exact_message_no_llm(config, clock):
    """Covers SRS error table: invalid URL."""
    app, llm, fetcher, _ = make(config, clock, {})
    r = app.test_client().post("/review", data={"url": "https://gitlab.com/a/b"})
    assert r.status_code == 400
    assert b"Please enter a public GitHub repository link." in r.data
    assert llm.calls == [] and fetcher.calls == []


@pytest.mark.parametrize("bad", ["", "   ", "javascript:alert(1)", "https://github.com/onlyowner",
                                 "https://user@github.com/a/b"])
def test_invalid_target_variants(config, clock, bad):
    """Covers SRS error table: malformed inputs refused, no LLM call."""
    app, llm, _, _ = make(config, clock, {})
    r = app.test_client().post("/review", data={"url": bad})
    assert r.status_code == 400
    assert llm.calls == []


def test_unreachable_target_exact_message_no_llm(config, clock):
    """Covers SRS error table: repository not downloadable."""
    app, llm, _, _ = make(config, clock, {})
    r = app.test_client().post("/review", data={"url": "https://github.com/no/body"})
    assert r.status_code == 400
    assert b"We could not download this repository. Is it public?" in r.data
    assert llm.calls == []


def test_no_key_exact_message(config, clock):
    """Covers D21/D23: real client without key -> 503 with exact review message."""
    app = create_app(config, clock=clock, fetcher=FakeRepoFetcher({TARGET: ex()}))
    r = app.test_client().post("/review", data={"url": TARGET})
    assert r.status_code == 503
    assert b"The review service is unavailable right now. Please try again later." in r.data


def test_llm_error_does_not_leak_peer_names(config, clock):
    """Covers D23: error page stays generic."""
    llm = FakeLLMClient(error=LLMUnavailableError("review"))
    app, _, _, rv = make(config, clock, {TARGET: ex(), PEER_B: ex()}, llm=llm)
    rv.set_peer_repos([PEER_B])
    r = app.test_client().post("/review", data={"url": TARGET})
    assert r.status_code == 503 and b"peer-b-example" not in r.data


# ---- rendering ----

def test_script_in_output_escaped(config, clock):
    """Covers NFR security: LLM output is escaped."""
    app, _, _, _ = make(config, clock, {TARGET: ex()}, reply="<script>alert(1)</script><img src=x onerror=1>")
    r = app.test_client().post("/review", data={"url": TARGET})
    assert b"<script>alert" not in r.data and b"<img src=x" not in r.data
    assert b"&lt;script&gt;" in r.data


def test_page_shows_peer_metrics_without_names(config, clock):
    """Covers FR-5.4: page shows labels and metrics, never peer identity."""
    app, _, _, rv = make(config, clock, {TARGET: ex(files=3, lines=42), PEER_B: ex(files=7, lines=111)},
                         reply="Compare with peer-b-example/secret-project")
    rv.set_peer_repos([PEER_B])
    r = app.test_client().post("/review", data={"url": TARGET})
    assert b"Submission B: 7 files, 111 lines" in r.data
    assert b"peer-b-example" not in r.data and b"secret-project" not in r.data


# ---- storage ----

def test_review_writes_nothing_to_db(config, clock):
    """Covers D11/OI-9: tables identical before and after a review (peer list set beforehand)."""
    app, _, _, rv = make(config, clock, {TARGET: ex(), PEER_B: ex()})
    rv.set_peer_repos([PEER_B])
    before = tables_snapshot(app)
    app.test_client().post("/review", data={"url": TARGET})
    app.test_client().post("/review", data={"url": "https://github.com/no/body"})
    assert tables_snapshot(app) == before


def test_only_peer_list_stored_by_peers_route(config, clock):
    """Covers D31: saving peers changes only the settings data."""
    app, _, _, _ = make(config, clock, {TARGET: ex()})
    before = tables_snapshot(app)
    c = app.test_client()
    login(c)
    c.post("/lecturer/peers", data={"urls": PEER_B})
    after = tables_snapshot(app)
    changed = {t for t in after if after[t] != before.get(t)}
    assert len(changed) == 1
    assert any(PEER_B in str(row) for row in after[changed.pop()])


# ---- auth and forms ----

def test_review_get_and_post_need_no_pin(config, clock):
    """Covers D12: F5 is PIN-free."""
    app, _, _, _ = make(config, clock, {TARGET: ex()})
    c = app.test_client()
    assert c.get("/review").status_code == 200
    assert c.post("/review", data={"url": TARGET}).status_code == 200


def test_peers_without_pin_redirects_to_login(config, clock):
    """Covers D31: same pattern as other lecturer pages (302 to login)."""
    app, _, _, rv = make(config, clock, {})
    c = app.test_client()
    for r in (c.get("/lecturer/peers"), c.post("/lecturer/peers", data={"urls": PEER_B})):
        assert r.status_code == 302
        assert "/lecturer/login" in r.headers["Location"]
    assert rv.peer_repos() == []


def test_peers_wrong_pin_still_blocked(config, clock):
    """Covers D31: wrong PIN gives no access."""
    app, _, _, _ = make(config, clock, {})
    c = app.test_client()
    c.post("/lecturer/login", data={"pin": "0000"})
    assert c.get("/lecturer/peers").status_code == 302


def test_peers_invalid_line_keeps_old_list_and_shows_text(config, clock):
    """Covers FR-5.5: one bad line -> 400, previous list kept, input redisplayed."""
    app, _, _, rv = make(config, clock, {})
    c = app.test_client()
    login(c)
    c.post("/lecturer/peers", data={"urls": PEER_B})
    r = c.post("/lecturer/peers", data={"urls": f"{PEER_C}\nnot a url"})
    assert r.status_code == 400
    assert b"Please enter a public GitHub repository link." in r.data
    assert rv.peer_repos() == [PEER_B]


def test_peers_save_canonicalises_and_replaces(config, clock):
    """Covers FR-5.5: .git/slash normalised, blank lines ignored, list replaced, empty clears."""
    app, _, _, rv = make(config, clock, {})
    c = app.test_client()
    login(c)
    c.post("/lecturer/peers", data={"urls": f"{PEER_B}.git\n\n  \n{PEER_C}/\n"})
    assert rv.peer_repos() == [PEER_B, PEER_C]
    c.post("/lecturer/peers", data={"urls": PEER_C})
    assert rv.peer_repos() == [PEER_C]
    c.post("/lecturer/peers", data={"urls": ""})
    assert rv.peer_repos() == []


def test_peers_page_escapes_text(config, clock):
    """Covers escaping: invalid input echoed back is escaped."""
    app, _, _, _ = make(config, clock, {})
    c = app.test_client()
    login(c)
    r = c.post("/lecturer/peers", data={"urls": "<script>alert(1)</script>"})
    assert r.status_code == 400
    assert b"<script>alert" not in r.data
