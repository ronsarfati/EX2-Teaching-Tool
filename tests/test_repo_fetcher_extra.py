"""T16 extra: URL table, zip-slip, zip bombs, network failures, ordering, truncation. urlopen is always mocked.

Covers FR-5.1, FR-5.2, D11, D21, D31.
"""
import builtins
import io
import logging
import os
import socket
import urllib.error
import zipfile
from unittest.mock import patch

import pytest

from app.adapters import repo_fetcher
from app.adapters.repo_fetcher import GitHubRepoFetcher
from app.errors import InvalidRepoUrlError, RepoUnavailableError

TARGET = "app.adapters.repo_fetcher.urlopen"
UNAVAILABLE = "We could not download this repository. Is it public?"
INVALID = "Please enter a public GitHub repository link."


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class Resp:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, n: int = -1) -> bytes:
        return self._data if n < 0 else self._data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fetch(data: bytes, max_chars: int = 50000, fetcher=None):
    with patch(TARGET, return_value=Resp(data)):
        return (fetcher or GitHubRepoFetcher()).fetch("https://github.com/o/r", max_chars)


# ---------- URL table ----------

@pytest.mark.parametrize("url,expected", [
    ("https://GitHub.COM/owner/repo", "https://github.com/owner/repo"),
    ("HTTPS://github.com/owner/repo", "https://github.com/owner/repo"),
    ("https://github.com/owner/repo.git/", "https://github.com/owner/repo"),
    ("https://github.com/my.owner/my.repo", "https://github.com/my.owner/my.repo"),
    ("https://github.com/my-owner/my_repo-2", "https://github.com/my-owner/my_repo-2"),
    ("\n\t https://github.com/owner/repo \n", "https://github.com/owner/repo"),
])
def test_normalize_accepts_table(url, expected):
    """Covers FR-5.1"""
    assert GitHubRepoFetcher().normalize_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://www.github.com/owner/repo",
    "https:///owner/repo",
    "https://github.com//repo",
    "https://github.com/owner/repo/issues/1",
    "https://github.com/owner/repo/tree/main/src",
    "javascript:alert(1)",
    "file:///etc/passwd",
    "ftp://github.com/owner/repo",
    "https://x@github.com/a/b",
    "https://user:pw@github.com/a/b",
    "https://github.com:8443/a/b",
    "github.com/owner/repo",
    "https://github.com/",
    "https://github.com/owner/repo name",
    "https://github.com/owner/..",
    "https://github.com/owner/.git",
    "   ",
])
def test_normalize_rejects_table(url):
    """Covers FR-5.1 error table"""
    with pytest.raises(InvalidRepoUrlError) as err:
        GitHubRepoFetcher().normalize_url(url)
    assert err.value.user_message == INVALID


def test_normalize_none_is_invalid():
    """Covers FR-5.1"""
    with pytest.raises(InvalidRepoUrlError):
        GitHubRepoFetcher().normalize_url(None)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [123, 4.5, b"https://github.com/a/b", ["https://github.com/a/b"]])
def test_normalize_non_str_is_invalid_not_crash(bad):
    """Covers FR-5.1: a non-string must give the user-facing error, not an AttributeError."""
    with pytest.raises(InvalidRepoUrlError):
        GitHubRepoFetcher().normalize_url(bad)  # type: ignore[arg-type]


def test_fetch_invalid_url_does_not_touch_network():
    with patch(TARGET) as mocked:
        with pytest.raises(InvalidRepoUrlError):
            GitHubRepoFetcher().fetch("https://evil.io/a/b", 1000)
    mocked.assert_not_called()


# ---------- request ----------

def test_request_is_canonical_codeload_with_timeout():
    """Covers D11"""
    with patch(TARGET, return_value=Resp(make_zip({"r-HEAD/a.py": "x"}))) as mocked:
        GitHubRepoFetcher().fetch("  HTTPS://GitHub.com/My.Owner/my-repo.git/ ", 1000)
    req = mocked.call_args.args[0]
    assert req.full_url == "https://codeload.github.com/My.Owner/my-repo/zip/HEAD"
    assert mocked.call_args.kwargs["timeout"] == 20


def test_custom_timeout_forwarded():
    with patch(TARGET, return_value=Resp(make_zip({"r-HEAD/a.py": "x"}))) as mocked:
        GitHubRepoFetcher(timeout_s=3).fetch("https://github.com/o/r", 1000)
    assert mocked.call_args.kwargs["timeout"] == 3


# ---------- network failures ----------

@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("u", 404, "Not Found", {}, None),
    urllib.error.HTTPError("u", 500, "Server Error", {}, None),
    urllib.error.URLError("dns failure"),
    socket.timeout("timed out"),
    TimeoutError("t"),
    ConnectionResetError("reset"),
])
def test_network_errors_become_unavailable(exc):
    """Covers FR-5.2 error table"""
    with patch(TARGET, side_effect=exc):
        with pytest.raises(RepoUnavailableError) as err:
            GitHubRepoFetcher().fetch("https://github.com/o/r", 1000)
    assert err.value.user_message == UNAVAILABLE


@pytest.mark.parametrize("body", [b"", b"this is not a zip", b"PK\x03\x04truncated"])
def test_bad_body_is_unavailable(body):
    with pytest.raises(RepoUnavailableError) as err:
        fetch(body)
    assert err.value.user_message == UNAVAILABLE


def test_body_over_download_cap_rejected():
    """Covers D31: 20 MB cap."""
    with pytest.raises(RepoUnavailableError):
        fetch(b"\0" * 20_000_001)


def test_body_exactly_at_cap_is_not_rejected_by_size():
    """At exactly 20 MB the size check passes; the junk then fails as a non-zip (still Unavailable)."""
    with pytest.raises(RepoUnavailableError):
        fetch(b"\0" * 20_000_000)


def test_download_read_is_bounded():
    """The adapter must not read more than cap+1 bytes from the response."""
    seen = []

    class Spy(Resp):
        def read(self, n=-1):
            seen.append(n)
            return super().read(n)

    with patch(TARGET, return_value=Spy(b"x")):
        with pytest.raises(RepoUnavailableError):
            GitHubRepoFetcher().fetch("https://github.com/o/r", 10)
    assert seen == [20_000_001]


def test_log_never_contains_full_exception_message(caplog):
    """Covers privacy: only the exception class name is logged."""
    secret = "SECRET-TOKEN-abc123 https://github.com/o/private"
    with caplog.at_level(logging.DEBUG):
        with patch(TARGET, side_effect=urllib.error.URLError(secret)):
            with pytest.raises(RepoUnavailableError):
                GitHubRepoFetcher().fetch("https://github.com/o/r", 1000)
    assert caplog.records
    assert "SECRET-TOKEN" not in caplog.text
    assert "URLError" in caplog.text


def test_unavailable_error_hides_cause():
    with patch(TARGET, side_effect=urllib.error.URLError("hidden detail")):
        with pytest.raises(RepoUnavailableError) as err:
            GitHubRepoFetcher().fetch("https://github.com/o/r", 1000)
    assert "hidden detail" not in str(err.value) + err.value.user_message
    assert err.value.__cause__ is None


# ---------- zip-slip ----------

def test_zip_slip_names_ignored_and_nothing_written(tmp_path, monkeypatch):
    """Covers D11: archive read in memory, nothing written to disk."""
    monkeypatch.chdir(tmp_path)
    data = make_zip({
        "r-HEAD/ok.py": "ok = 1\n",
        "r-HEAD/../x.py": "evil = 1\n",
        "/etc/x.py": "evil = 2\n",
        "a/../../x.py": "evil = 3\n",
        "../x.py": "evil = 4\n",
    })
    real_open = builtins.open
    writes = []

    def spy_open(file, mode="r", *a, **k):
        if any(c in str(mode) for c in "wax+"):
            writes.append(file)
        return real_open(file, mode, *a, **k)

    with patch.object(builtins, "open", spy_open), \
         patch.object(zipfile.ZipFile, "extract", side_effect=AssertionError("extract")), \
         patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError("extractall")):
        result = fetch(data)
    assert "ok = 1" in result.text
    assert "evil" not in result.text
    assert result.file_count == 1
    assert writes == []
    assert os.listdir(tmp_path) == []
    assert not (tmp_path.parent / "x.py").exists()


def test_zip_slip_only_returns_empty_extract():
    result = fetch(make_zip({"../x.py": "evil", "/abs.py": "evil"}))
    assert result.text == "" and result.file_count == 0 and result.truncated is False


# ---------- zip bombs ----------

def test_declared_size_over_cap_rejected():
    """Covers D31: 61 MB declared decompressed (compresses to a few KB)."""
    data = make_zip({"r-HEAD/big.py": "0" * 61_000_000})
    assert len(data) < 1_000_000
    with pytest.raises(RepoUnavailableError) as err:
        fetch(data)
    assert err.value.user_message == UNAVAILABLE


def test_declared_size_sum_over_cap_rejected(monkeypatch):
    monkeypatch.setattr(repo_fetcher, "_MAX_UNCOMPRESSED_BYTES", 1000)
    data = make_zip({"r-HEAD/a.py": "a" * 600, "r-HEAD/b.py": "b" * 600})
    with pytest.raises(RepoUnavailableError):
        fetch(data)


def test_declared_size_at_cap_accepted(monkeypatch):
    monkeypatch.setattr(repo_fetcher, "_MAX_UNCOMPRESSED_BYTES", 1200)
    data = make_zip({"r-HEAD/a.py": "a" * 600, "r-HEAD/b.py": "b" * 600})
    assert fetch(data).file_count == 2


def test_member_real_size_exceeds_header_stays_bounded():
    """A lying header (declares 10 bytes, holds 500 000): result is bounded or Unavailable, never huge."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("r-HEAD/a.py", "z" * 500_000)
        zf.infolist()[0].file_size = 10
    try:
        result = fetch(buf.getvalue(), max_chars=1_000_000)
    except RepoUnavailableError:
        return
    assert len(result.text) <= 200_100


def test_per_file_cap_200kb():
    """Covers D31: one 500 KB file is cut at 200 000 chars."""
    result = fetch(make_zip({"r-HEAD/big.py": "a" * 500_000}), max_chars=1_000_000)
    assert result.text == "=== big.py ===\n" + "a" * 200_000 + "\n"
    assert result.truncated is False


# ---------- selection and ordering ----------

def test_no_readme_still_works():
    result = fetch(make_zip({"r-HEAD/b.py": "b\n", "r-HEAD/a.py": "a\n"}))
    assert result.text.index("=== a.py") < result.text.index("=== b.py")
    assert result.file_count == 2


def test_readme_in_root_first_regardless_of_case():
    result = fetch(make_zip({"r-HEAD/a.py": "a\n", "r-HEAD/ReadMe.MD": "doc\n", "r-HEAD/0.py": "z\n"}))
    assert result.text.startswith("=== ReadMe.MD ===\ndoc\n")


def test_readme_in_subfolder_not_first():
    result = fetch(make_zip({"r-HEAD/a.py": "a\n", "r-HEAD/docs/README.md": "doc\n"}))
    assert result.text.startswith("=== a.py ===")
    assert "=== docs/README.md ===" in result.text


@pytest.mark.parametrize("folder", ["node_modules", ".venv", "venv", ".git", "dist", "build", "__pycache__"])
def test_skipped_dirs(folder):
    result = fetch(make_zip({f"r-HEAD/{folder}/x.py": "bad\n", f"r-HEAD/src/{folder}/y.py": "bad\n",
                             "r-HEAD/ok.py": "ok\n"}))
    assert "bad" not in result.text
    assert result.file_count == 1


def test_binary_and_image_files_excluded_from_text():
    result = fetch(make_zip({"r-HEAD/logo.png": "PNGDATA", "r-HEAD/app.exe": "MZ", "r-HEAD/data.bin": "00",
                             "r-HEAD/ok.py": "ok\n"}))
    assert "PNGDATA" not in result.text and "MZ" not in result.text
    assert "=== ok.py ===" in result.text


def test_non_utf8_bytes_do_not_crash():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("r-HEAD/latin.py", b"caf\xe9 = 1\n\xff\xfe")
    result = fetch(buf.getvalue())
    assert "=== latin.py ===" in result.text
    assert "caf" in result.text


def test_directory_entries_ignored():
    result = fetch(make_zip({"r-HEAD/": "", "r-HEAD/src/": "", "r-HEAD/src/a.py": "a\n"}))
    assert result.file_count == 1


# ---------- max_chars boundary ----------

BLOCK = "=== a.py ===\nabc\n"  # 16 chars


def test_max_chars_exactly_block_length_not_truncated():
    result = fetch(make_zip({"r-HEAD/a.py": "abc"}), max_chars=len(BLOCK))
    assert result.text == BLOCK and result.truncated is False


def test_max_chars_one_less_is_truncated():
    result = fetch(make_zip({"r-HEAD/a.py": "abc"}), max_chars=len(BLOCK) - 1)
    assert result.text == BLOCK[:-1] and result.truncated is True


def test_max_chars_zero_gives_empty_truncated():
    result = fetch(make_zip({"r-HEAD/a.py": "abc"}), max_chars=0)
    assert result.text == "" and result.truncated is True


def test_truncation_never_exceeds_max_chars_over_many_files():
    files = {f"r-HEAD/f{i}.py": "x" * 50 for i in range(10)}
    result = fetch(make_zip(files), max_chars=120)
    assert len(result.text) == 120 and result.truncated is True


def test_line_count_without_trailing_newline():
    result = fetch(make_zip({"r-HEAD/a.py": "a\nb\nc"}))
    assert result.line_count == 3
