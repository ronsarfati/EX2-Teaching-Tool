"""Public GitHub repository access (D11): the `RepoFetcher` port and its zip-archive adapter, used by F5.

The archive is read in memory only: nothing from the repository is ever written to disk or executed.
"""
from __future__ import annotations

import io
import logging
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.errors import InvalidRepoUrlError, RepoUnavailableError

_LOG = logging.getLogger(__name__)

# GitHub owner / repository names: letters, digits, '-', '_', '.' (no slash, no spaces).
_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_SOURCE_EXTENSIONS = (".py", ".java", ".js", ".ts", ".cs", ".cpp", ".c", ".h", ".md")
# Vendored, generated or environment folders add noise and size, not student work.
_SKIPPED_DIRS = frozenset({"node_modules", ".git", "venv", ".venv", "build", "dist", "__pycache__"})
_MAX_FILE_BYTES = 200_000  # per-file read cap: one huge file must not eat the whole budget
_MAX_UNCOMPRESSED_BYTES = 60_000_000  # zip-bomb guard on the declared total size


@dataclass(frozen=True)
class RepoExtract:
    """What the reviewer needs from a repository: capped text plus size metrics."""

    text: str
    file_count: int
    line_count: int
    truncated: bool


class RepoFetcher(Protocol):
    """Turns a repository URL into a `RepoExtract`; swapped for a fake in tests (no network)."""

    def normalize_url(self, url: str) -> str: ...

    def fetch(self, url: str, max_chars: int) -> RepoExtract: ...


class GitHubRepoFetcher:
    """Downloads the public archive of a GitHub repository without any token."""

    def __init__(self, timeout_s: float = 20, max_archive_bytes: int = 20_000_000) -> None:
        self._timeout_s = timeout_s
        self._max_archive_bytes = max_archive_bytes

    def normalize_url(self, url: str) -> str:
        """Return `https://github.com/<owner>/<repo>`; anything else is an `InvalidRepoUrlError`."""
        if not isinstance(url, str):
            raise InvalidRepoUrlError()
        parts = urlsplit(url.strip())  # query and fragment are parsed apart, then dropped
        # Userinfo ("user@github.com") is a classic URL-spoofing trick: refuse it.
        if parts.scheme != "https" or (parts.hostname or "").lower() != "github.com" or parts.port:
            raise InvalidRepoUrlError()
        if "@" in parts.netloc:
            raise InvalidRepoUrlError()
        segments = parts.path.strip("/").split("/")
        if len(segments) != 2:
            raise InvalidRepoUrlError()
        owner, repo = segments
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        if not _NAME.match(owner) or not _NAME.match(repo) or repo in (".", ".."):
            raise InvalidRepoUrlError()
        return f"https://github.com/{owner}/{repo}"

    def fetch(self, url: str, max_chars: int) -> RepoExtract:
        canonical = self.normalize_url(url)
        archive = self._download(canonical.replace("https://github.com/", "https://codeload.github.com/") + "/zip/HEAD")
        try:
            return _extract(archive, max_chars)
        except (zipfile.BadZipFile, ValueError, RuntimeError, OSError):
            raise RepoUnavailableError() from None

    def _download(self, archive_url: str) -> bytes:
        """GET the zip with a timeout and a size cap; every failure becomes `RepoUnavailableError`."""
        try:
            with urlopen(Request(archive_url, headers={"User-Agent": "teaching-tool"}), timeout=self._timeout_s) as resp:
                data = resp.read(self._max_archive_bytes + 1)
        except Exception as exc:  # noqa: BLE001 - HTTP 404, timeout, DNS: one user-facing error
            _LOG.warning("Repository download failed: %s", type(exc).__name__)
            raise RepoUnavailableError() from None
        if len(data) > self._max_archive_bytes:
            raise RepoUnavailableError()
        return data


def _relative_path(name: str) -> str | None:
    """Drop the archive's top folder ("repo-HEAD/"); None for unsafe or directory entries."""
    if name.endswith("/") or name.startswith("/") or ".." in name.split("/"):
        return None
    _, _, rest = name.partition("/")
    return posixpath.normpath(rest) if rest else None


def _is_readme(path: str) -> bool:
    return "/" not in path and path.lower().startswith("readme")


def _is_source(path: str) -> bool:
    return path.lower().endswith(_SOURCE_EXTENSIONS)


def _extract(archive: bytes, max_chars: int) -> RepoExtract:
    """Read the zip in memory: README first, then source files in path order, within `max_chars`."""
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        if sum(info.file_size for info in zf.infolist()) > _MAX_UNCOMPRESSED_BYTES:
            raise ValueError("archive too large once decompressed")
        entries = []
        for info in zf.infolist():
            path = _relative_path(info.filename)
            if path is None or _SKIPPED_DIRS.intersection(path.split("/")[:-1]):
                continue
            entries.append((path, info))
        entries.sort(key=lambda item: (not _is_readme(item[0]), item[0]))

        chunks: list[str] = []
        used = 0
        lines = 0
        truncated = False
        for path, info in entries:
            if not (_is_source(path) or _is_readme(path)):
                continue
            with zf.open(info) as handle:
                content = handle.read(_MAX_FILE_BYTES).decode("utf-8", errors="replace")
            lines += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            block = f"=== {path} ===\n{content}\n"
            room = max_chars - used
            if len(block) > room:
                truncated = True
                block = block[:room]
            chunks.append(block)
            used += len(block)
    return RepoExtract("".join(chunks), len(entries), lines, truncated)
