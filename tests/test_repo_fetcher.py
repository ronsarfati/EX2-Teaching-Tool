"""T16: URL validation and in-memory zip extraction. No network: `urlopen` is mocked."""
import io
import urllib.error
import zipfile
from unittest.mock import patch

import pytest

from app.adapters.repo_fetcher import GitHubRepoFetcher
from app.errors import InvalidRepoUrlError, RepoUnavailableError
from tests.fakes import FakeRepoFetcher

TARGET = "app.adapters.repo_fetcher.urlopen"


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, n: int = -1) -> bytes:
        return self._data if n < 0 else self._data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fetch_with(data: bytes, max_chars: int = 50000, fetcher: GitHubRepoFetcher | None = None):
    with patch(TARGET, return_value=FakeResponse(data)) as mocked:
        result = (fetcher or GitHubRepoFetcher()).fetch("https://github.com/demo-owner/demo-repo", max_chars)
    return result, mocked


@pytest.mark.parametrize("url", [
    "https://github.com/demo-owner/demo-repo",
    "https://github.com/demo-owner/demo-repo.git",
    "https://github.com/demo-owner/demo-repo/",
    "  https://github.com/demo-owner/demo-repo?tab=readme#top ",
])
def test_normalize_accepts(url):
    assert GitHubRepoFetcher().normalize_url(url) == "https://github.com/demo-owner/demo-repo"


@pytest.mark.parametrize("url", [
    "", "http://github.com/demo-owner/demo-repo", "https://gitlab.com/demo-owner/demo-repo",
    "https://github.com/demo-owner", "https://github.com/demo-owner/demo-repo/tree/main",
    "https://github.com.evil.io/demo-owner/demo-repo", "https://github.com/demo owner/repo",
])
def test_normalize_rejects(url):
    with pytest.raises(InvalidRepoUrlError) as err:
        GitHubRepoFetcher().normalize_url(url)
    assert err.value.user_message == "Please enter a public GitHub repository link."


def test_fetch_uses_codeload_and_orders_readme_first():
    data = make_zip({
        "demo-repo-HEAD/a.py": "print(1)\nprint(2)\n",
        "demo-repo-HEAD/README.md": "# Demo\n",
        "demo-repo-HEAD/src/b.java": "class B {}",
    })
    result, mocked = fetch_with(data)
    request = mocked.call_args.args[0]
    assert request.full_url == "https://codeload.github.com/demo-owner/demo-repo/zip/HEAD"
    assert result.text.index("README.md") < result.text.index("a.py") < result.text.index("b.java")
    assert (result.file_count, result.line_count, result.truncated) == (3, 4, False)


def test_vendored_and_binary_files_skipped():
    data = make_zip({
        "r-HEAD/main.py": "x = 1\n",
        "r-HEAD/node_modules/lib/index.js": "bad\n",
        "r-HEAD/.venv/x.py": "bad\n",
        "r-HEAD/dist/out.js": "bad\n",
        "r-HEAD/logo.png": "binary",
    })
    result, _ = fetch_with(data)
    assert "bad" not in result.text and "logo.png" not in result.text
    assert result.file_count == 2  # main.py and the image (counted, not read)
    assert result.line_count == 1


def test_text_is_capped():
    data = make_zip({"r-HEAD/big.py": "x = 1\n" * 20000, "r-HEAD/README.md": "hi\n"})
    result, _ = fetch_with(data, max_chars=1000)
    assert len(result.text) <= 1000 and result.truncated
    assert result.text.startswith("=== README.md")
    assert result.line_count > 1000


def test_zip_slip_names_ignored():
    data = make_zip({"r-HEAD/../evil.py": "x\n", "/abs.py": "x\n", "r-HEAD/ok.py": "y\n"})
    result, _ = fetch_with(data)
    assert "evil" not in result.text and "abs.py" not in result.text and "ok.py" in result.text


def test_decompressed_size_cap():
    data = make_zip({"r-HEAD/zeros.py": "0" * 70_000_000})
    with pytest.raises(RepoUnavailableError):
        fetch_with(data)


def test_archive_over_cap_is_unavailable():
    with pytest.raises(RepoUnavailableError):
        fetch_with(b"x" * 101, fetcher=GitHubRepoFetcher(max_archive_bytes=100))


@pytest.mark.parametrize("failure", [
    urllib.error.HTTPError("u", 404, "Not Found", None, None), urllib.error.URLError("down"), TimeoutError(),
])
def test_network_errors_are_unavailable(failure):
    with patch(TARGET, side_effect=failure):
        with pytest.raises(RepoUnavailableError) as err:
            GitHubRepoFetcher().fetch("https://github.com/demo-owner/demo-repo", 1000)
    assert err.value.user_message == "We could not download this repository. Is it public?"


def test_not_a_zip_is_unavailable():
    with pytest.raises(RepoUnavailableError):
        fetch_with(b"<html>not a zip</html>")


def test_invalid_url_never_hits_network():
    with patch(TARGET) as mocked:
        with pytest.raises(InvalidRepoUrlError):
            GitHubRepoFetcher().fetch("https://example.com/a/b", 1000)
    mocked.assert_not_called()


def test_fake_fetcher():
    fake = FakeRepoFetcher({"https://github.com/a/b": "EXTRACT"})
    assert fake.fetch("https://github.com/a/b.git", 5) == "EXTRACT"
    assert fake.calls == [("https://github.com/a/b", 5)]
    with pytest.raises(RepoUnavailableError):
        fake.fetch("https://github.com/a/zzz", 5)
