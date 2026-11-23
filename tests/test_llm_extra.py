"""Extra ClaudeClient tests, SDK fully mocked (no network, no key). Covers T15, D12, D23, FR-5.3, FR-4.4."""
import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.adapters import llm
from app.adapters.llm import ClaudeClient
from app.config import Config
from app.errors import LLMUnavailableError

KEY = "sk-secret-key-XYZ"
SECRET_PROMPT = "TOP SECRET PROMPT TEXT"
SECRET_MSG = f"detail {KEY} {SECRET_PROMPT}"
REQ = httpx.Request("POST", "https://x")


def _resp(status):
    return httpx.Response(status, request=REQ)


class FakeSDK:
    instances: list = []
    error = None
    content: list = []

    def __init__(self, **kwargs):
        self.init = kwargs
        self.kwargs = None
        self.messages = SimpleNamespace(create=self._create)
        FakeSDK.instances.append(self)

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if FakeSDK.error:
            raise FakeSDK.error
        return SimpleNamespace(content=FakeSDK.content)


@pytest.fixture(autouse=True)
def sdk(monkeypatch):
    FakeSDK.instances, FakeSDK.error = [], None
    FakeSDK.content = [SimpleNamespace(type="text", text="ok")]
    monkeypatch.setattr(llm.anthropic, "Anthropic", FakeSDK)
    return FakeSDK


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _msg(feature):
    return f"The {feature} service is unavailable right now. Please try again later."


@pytest.mark.parametrize("key", [None, "", "   ", "\t\n"])
@pytest.mark.parametrize("feature", ["review", "summary"])
def test_blank_key_never_builds_sdk(sdk, key, feature):
    """Covers T15, NFR-9, FR-4.4: missing/blank key -> unavailable, SDK never constructed."""
    with pytest.raises(LLMUnavailableError) as e:
        ClaudeClient(key, "m").complete("s", "p", 10, feature=feature)
    assert sdk.instances == []
    assert e.value.user_message == _msg(feature)


ERRORS = [
    lambda: anthropic.APIConnectionError(request=REQ),
    lambda: anthropic.APITimeoutError(request=REQ),
    lambda: anthropic.RateLimitError(SECRET_MSG, response=_resp(429), body=None),
    lambda: anthropic.AuthenticationError(SECRET_MSG, response=_resp(401), body=None),
    lambda: anthropic.APIStatusError(SECRET_MSG, response=_resp(500), body=None),
    lambda: Exception(SECRET_MSG),
]


@pytest.mark.parametrize("make", ERRORS)
@pytest.mark.parametrize("feature", ["review", "summary"])
def test_every_failure_maps_to_exact_message_without_leak(sdk, make, feature, caplog):
    """Covers T15, FR-5.3, FR-4.4, error table: exact wording, no key/prompt/exception text leaked."""
    sdk.error = make()
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMUnavailableError) as e:
            ClaudeClient(KEY, "m").complete("s", SECRET_PROMPT, 10, feature=feature)
    shown = e.value.user_message + str(e.value)
    assert e.value.user_message == _msg(feature)
    assert e.value.feature == feature
    for secret in (KEY, SECRET_PROMPT, "detail"):
        assert secret not in shown
        assert secret not in caplog.text


def test_default_feature_is_review(sdk):
    """Covers T15: default feature wording is 'review'."""
    sdk.error = Exception("x")
    with pytest.raises(LLMUnavailableError) as e:
        ClaudeClient(KEY, "m").complete("s", "p", 1)
    assert e.value.user_message == _msg("review")


def test_config_default_model_and_override():
    """Covers D12, D23: default model claude-sonnet-5-5 when ANTHROPIC_MODEL unset; env overrides."""
    base = {"LECTURER_PIN": "1", "SECRET_KEY": "k", "BASE_URL": "http://x"}
    assert Config.from_env(base).anthropic_model == "claude-sonnet-5-5"
    assert Config.from_env({**base, "ANTHROPIC_MODEL": ""}).anthropic_model == "claude-sonnet-5-5"
    assert Config.from_env({**base, "ANTHROPIC_MODEL": "other"}).anthropic_model == "other"
    assert Config.from_env(base).anthropic_api_key is None


def test_model_from_constructor_reaches_sdk(sdk):
    """Covers D12: model comes from the constructor; timeout and retries configured."""
    ClaudeClient(KEY, Config.from_env(
        {"LECTURER_PIN": "1", "SECRET_KEY": "k", "BASE_URL": "http://x"}).anthropic_model).complete("s", "p", 1)
    assert sdk.instances[0].kwargs["model"] == "claude-sonnet-5-5"
    ClaudeClient(KEY, "custom-model", timeout_s=7).complete("s", "p", 1)
    assert sdk.instances[1].kwargs["model"] == "custom-model"
    assert sdk.instances[1].init == {"api_key": KEY, "timeout": 7, "max_retries": 1}


def test_max_tokens_and_system_forwarded(sdk):
    """Covers T15: max_tokens, system and prompt forwarded unchanged."""
    ClaudeClient(KEY, "m").complete("SYS TEXT", "USER TEXT", 4096)
    kw = sdk.instances[0].kwargs
    assert kw["max_tokens"] == 4096 and kw["system"] == "SYS TEXT"
    assert kw["messages"] == [{"role": "user", "content": "USER TEXT"}]


def test_multiple_text_blocks_concatenated(sdk):
    """Covers T15: text blocks are concatenated in order."""
    sdk.content = [_text("a"), _text("b"), _text("c")]
    assert ClaudeClient(KEY, "m").complete("s", "p", 1) == "abc"


def test_non_text_blocks_ignored(sdk):
    """Covers T15: non-text blocks (tool_use, thinking) are skipped."""
    sdk.content = [SimpleNamespace(type="thinking", thinking="hmm"), _text("x"),
                   SimpleNamespace(type="tool_use", name="t"), _text("y")]
    assert ClaudeClient(KEY, "m").complete("s", "p", 1) == "xy"


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="tool_use")]])
def test_no_text_block_returns_empty_string(sdk, content):
    """Covers T15: current behaviour for a reply with no text block is '' (spec silent; see report)."""
    sdk.content = content
    assert ClaudeClient(KEY, "m").complete("s", "p", 1) == ""
