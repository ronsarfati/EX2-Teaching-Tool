"""ClaudeClient with a mocked SDK (no network, no key) and FakeLLMClient."""
import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.adapters import llm
from app.adapters.llm import ClaudeClient
from app.errors import LLMUnavailableError
from tests.fakes import FakeLLMClient

KEY = "sk-secret-key-123"


class FakeSDK:
    """Stands in for anthropic.Anthropic; remembers constructor and call arguments."""

    instances: list = []
    error: Exception | None = None

    def __init__(self, **kwargs):
        self.init = kwargs
        self.kwargs = None
        self.messages = SimpleNamespace(create=self._create)
        FakeSDK.instances.append(self)

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if FakeSDK.error:
            raise FakeSDK.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="hello")])


@pytest.fixture(autouse=True)
def sdk(monkeypatch):
    FakeSDK.instances, FakeSDK.error = [], None
    monkeypatch.setattr(llm.anthropic, "Anthropic", FakeSDK)
    return FakeSDK


def test_returns_text_and_passes_arguments(sdk):
    assert ClaudeClient(KEY, "model-x").complete("sys", "prompt", 123) == "hello"
    inst = sdk.instances[0]
    assert inst.init["api_key"] == KEY and inst.init["timeout"] > 0
    assert inst.kwargs == {"model": "model-x", "max_tokens": 123, "system": "sys",
                           "messages": [{"role": "user", "content": "prompt"}]}


@pytest.mark.parametrize("key", [None, ""])
def test_no_key_means_no_sdk_call(sdk, key):
    with pytest.raises(LLMUnavailableError) as e:
        ClaudeClient(key, "m").complete("s", "p", 10, feature="summary")
    assert sdk.instances == []
    assert e.value.user_message == "The summary service is unavailable right now. Please try again later."


@pytest.mark.parametrize("error", [
    anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")),
    anthropic.APITimeoutError(request=httpx.Request("POST", "https://x")),
    RuntimeError(f"boom {KEY} SECRET PROMPT"),
])
def test_sdk_errors_become_unavailable_without_leak(sdk, error, caplog):
    sdk.error = error
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LLMUnavailableError) as e:
            ClaudeClient(KEY, "m").complete("s", "SECRET PROMPT", 10)
    assert e.value.user_message == "The review service is unavailable right now. Please try again later."
    assert e.value.__cause__ is None
    assert KEY not in caplog.text and "SECRET PROMPT" not in caplog.text
    assert type(error).__name__ in caplog.text


def test_fake_client_records_and_fails():
    fake = FakeLLMClient(reply=lambda p: p.upper())
    assert fake.complete("s", "abc", 5) == "ABC"
    assert fake.calls == [{"system": "s", "prompt": "abc", "max_tokens": 5}]
    with pytest.raises(LLMUnavailableError):
        FakeLLMClient(error=LLMUnavailableError("summary")).complete("s", "p", 1)
