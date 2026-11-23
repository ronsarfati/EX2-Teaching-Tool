"""Homework review (F5, FR-5.1-FR-5.5, D11, D31): fetch, build one anonymised prompt, ask the LLM.

Nothing is persisted except the lecturer's list of comparison repositories (OI-1); reviews are not stored (OI-9).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.adapters.llm import LLMClient
from app.adapters.repo_fetcher import RepoExtract, RepoFetcher
from app.errors import RepoUnavailableError
from app.repositories.settings import SettingsRepository

SYSTEM_PROMPT = (
    "You are a teaching assistant reviewing a student's programming homework. Be concise and constructive. "
    "Never name any person, account, repository or URL: refer to other work only as 'Submission B' or "
    "'Submission C'."
)
RUBRIC = (
    "Review Submission A against this rubric: (1) purpose and README, (2) structure and OOP design, "
    "(3) code quality, (4) tests, (5) the top 3 improvements. Then compare it with the other submissions, if any."
)
NO_PEER_SENTENCE = "No other submission was available for comparison."


@dataclass(frozen=True)
class ReviewResult:
    """What the review page shows. Metrics are deterministic counts, not LLM output."""

    review_text: str
    target_metrics: RepoExtract
    peer_metrics: dict[str, RepoExtract] = field(default_factory=dict)  # keyed by label ("Submission B")
    comparison_available: bool = False


class HomeworkReviewer:
    MAX_PEERS = 2
    TARGET_CAP_CHARS = 50_000
    PEER_CAP_CHARS = 15_000
    MAX_TOKENS = 1500  # bounds cost and latency of one review (OI-10)
    SETTING_KIND = "peer_repo"

    def __init__(self, fetcher: RepoFetcher, llm: LLMClient, settings: SettingsRepository) -> None:
        self._fetcher = fetcher
        self._llm = llm
        self._settings = settings

    def review(self, repo_url: str) -> ReviewResult:
        """Review one public repository; raises InvalidRepoUrlError, RepoUnavailableError or LLMUnavailableError."""
        target_url = self._fetcher.normalize_url(repo_url)
        target = self._fetcher.fetch(target_url, self.TARGET_CAP_CHARS)
        peers = self._fetch_peers(target_url)  # [(label, url, extract)]
        prompt = self._build_prompt(target, peers)
        reply = self._llm.complete(SYSTEM_PROMPT, prompt, self.MAX_TOKENS, feature="review")
        return ReviewResult(_redact(reply, peers), target, {label: ex for label, _, ex in peers}, bool(peers))

    def peer_repos(self) -> list[str]:
        return self._settings.list_values(self.SETTING_KIND)

    def set_peer_repos(self, urls: list[str]) -> None:
        """Validate every URL first (one bad line keeps the stored list), then replace the list."""
        canonical = [self._fetcher.normalize_url(url) for url in urls if url.strip()]
        self._settings.replace_values(self.SETTING_KIND, canonical)

    def _fetch_peers(self, target_url: str) -> list[tuple[str, str, RepoExtract]]:
        """Take the first MAX_PEERS listed repositories other than the target; unreachable ones are skipped."""
        candidates = [u for u in self.peer_repos() if u.lower() != target_url.lower()][: self.MAX_PEERS]
        peers = []
        for url in candidates:
            try:
                extract = self._fetcher.fetch(url, self.PEER_CAP_CHARS)
            except RepoUnavailableError:
                continue
            peers.append((f"Submission {chr(ord('B') + len(peers))}", url, extract))
        return peers

    @staticmethod
    def _build_prompt(target: RepoExtract, peers: list[tuple[str, str, RepoExtract]]) -> str:
        parts = [RUBRIC, _section("Submission A", target)]
        for label, _, extract in peers:
            # Names are masked inside the code too: READMEs often carry the author's account.
            masked = RepoExtract(_redact(extract.text, peers), extract.file_count,
                                 extract.line_count, extract.truncated)
            parts.append(_section(label, masked))
        return "\n\n".join(parts)


def _section(label: str, extract: RepoExtract) -> str:
    note = " (text truncated)" if extract.truncated else ""
    return (f"## {label}\nMetrics: {extract.file_count} files, {extract.line_count} lines{note}\n"
            f"{extract.text}")


def _redact(text: str, peers: list[tuple[str, str, RepoExtract]]) -> str:
    """Replace every peer URL, then its owner and repository names, by the peer's label (FR-5.4).

    Case-insensitive. A name glued to other text by '-', '_' or '.' is masked; one inside a longer run of
    letters or digits ("malice" for "alice") is left alone.
    """
    for label, url, _ in peers:
        text = re.sub(re.escape(url), label, text, flags=re.IGNORECASE)
        for name in url.rstrip("/").split("/")[-2:]:  # owner, repository
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", label, text,
                          flags=re.IGNORECASE)
    return text
