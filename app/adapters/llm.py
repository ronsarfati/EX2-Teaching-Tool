"""LLM access (D12): the `LLMClient` port and its Anthropic (Claude) adapter, shared by F4 and F5."""
from __future__ import annotations

import logging
from typing import Optional, Protocol

import anthropic

from app.errors import LLMUnavailableError

_LOG = logging.getLogger(__name__)


class LLMClient(Protocol):
    """One text-in, text-out call. `feature` ("review"/"summary") only selects the error wording."""

    def complete(self, system: str, prompt: str, max_tokens: int, feature: str = "review") -> str: ...


class ClaudeClient:
    """Claude through the official SDK. Without a key nothing is sent over the network (NFR-9)."""

    def __init__(self, api_key: Optional[str], model: str, timeout_s: float = 60) -> None:
        self._api_key = (api_key or "").strip()  # a blank key counts as missing
        self._model = model
        self._timeout_s = timeout_s

    def complete(self, system: str, prompt: str, max_tokens: int, feature: str = "review") -> str:
        if not self._api_key:
            raise LLMUnavailableError(feature)
        try:
            client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout_s, max_retries=1)
            message = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        except Exception as exc:  # noqa: BLE001 - every SDK/network failure maps to one user-facing error
            # Only the class name is logged: the message could contain the prompt or the key.
            _LOG.warning("LLM call failed: %s", type(exc).__name__)
            raise LLMUnavailableError(feature) from None
