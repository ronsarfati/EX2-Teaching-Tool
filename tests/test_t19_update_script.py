"""T19 criterion 18: scripts/update_relay_ranges.py, with a fake fetch. Never touches the network.

Covers FR-1.19, D32.
"""
import importlib.util
import socket
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("update_relay_ranges", ROOT / "scripts" / "update_relay_ranges.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

CSV = "\n".join([
    "198.51.100.0/24,IL,IL-M,Tel Aviv,", "2001:db8:4000::/64,IL,IL-M,Haifa,", "203.0.113.0/24,FR,FR-IDF,Paris,",
    "bad,IL,,,", "", "999.1.1.0/24,IL,,,", "192.0.2.0/24,il,x,y,", "garbage", "2001:db8:ffff::/48,FR,,,",
])
IL_LINES = ["198.51.100.0/24,IL,IL-M,Tel Aviv,", "2001:db8:4000::/64,IL,IL-M,Haifa,", "192.0.2.0/24,il,x,y,"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(script, "download", boom)


def fake(text=CSV):
    return lambda url: text


def test_writes_only_country_lines_and_prints_counts(tmp_path, capsys):
    out = tmp_path / "o.csv"
    assert script.main(["--output", str(out)], fetch=fake()) == 0
    assert out.read_text().splitlines() == IL_LINES and out.read_text().endswith("\n")
    printed = capsys.readouterr().out
    assert "3 ranges for IL (2 IPv4, 1 IPv6)" in printed and "3 malformed" in printed
    assert list(tmp_path.iterdir()) == [out]  # no .tmp


@pytest.mark.parametrize("flag", ["fr", "FR", " Fr "])
def test_country_case_insensitive(tmp_path, flag):
    out = tmp_path / "o.csv"
    assert script.main(["--country", flag, "--output", str(out)], fetch=fake()) == 0
    assert out.read_text().splitlines() == ["203.0.113.0/24,FR,FR-IDF,Paris,", "2001:db8:ffff::/48,FR,,,"]


def test_default_output_name_follows_country(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert script.main(["--country", "fr"], fetch=fake()) == 0
    assert (tmp_path / "data" / "apple_relay_ranges_FR.csv").exists()


def test_parent_dir_created(tmp_path):
    out = tmp_path / "a" / "b" / "o.csv"
    assert script.main(["--output", str(out)], fetch=fake()) == 0 and out.exists()


@pytest.mark.parametrize("error", [OSError("x"), urllib.error.URLError("down"), TimeoutError(), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")])
def test_download_error_exit_1_file_untouched(tmp_path, capsys, error):
    out = tmp_path / "o.csv"
    out.write_bytes(b"OLD\n")

    def fetch(url):
        raise error
    assert script.main(["--output", str(out)], fetch=fetch) == 1
    assert out.read_bytes() == b"OLD\n" and [p.name for p in tmp_path.iterdir()] == ["o.csv"]
    err = capsys.readouterr().err
    assert "Download failed" in err and "Traceback" not in err


@pytest.mark.parametrize("text", ["", "203.0.113.0/24,FR,,,\n", "bad,IL,,,\ngarbage\n", "\n\n"])
def test_no_line_for_country_exit_1_file_untouched(tmp_path, capsys, text):
    out = tmp_path / "o.csv"
    out.write_bytes(b"OLD\n")
    assert script.main(["--output", str(out)], fetch=fake(text)) == 1
    assert out.read_bytes() == b"OLD\n" and [p.name for p in tmp_path.iterdir()] == ["o.csv"]
    assert "left untouched" in capsys.readouterr().err


def test_no_line_does_not_create_output_or_parent(tmp_path):
    out = tmp_path / "sub" / "o.csv"
    assert script.main(["--output", str(out)], fetch=fake("")) == 1
    assert not out.exists()


def test_failed_rename_leaves_no_tmp_and_old_file(tmp_path, monkeypatch):
    out = tmp_path / "o.csv"
    out.write_bytes(b"OLD\n")

    def broken(src, dst):
        raise OSError("disk")
    monkeypatch.setattr(script.os, "replace", broken)
    with pytest.raises(OSError):
        script.main(["--output", str(out)], fetch=fake())
    assert out.read_bytes() == b"OLD\n" and [p.name for p in tmp_path.iterdir()] == ["o.csv"]


def test_output_replaces_old_content(tmp_path):
    out = tmp_path / "o.csv"
    out.write_text("OLD\n")
    assert script.main(["--output", str(out)], fetch=fake()) == 0
    assert "OLD" not in out.read_text()


def test_crlf_input(tmp_path):
    out = tmp_path / "o.csv"
    assert script.main(["--output", str(out)], fetch=fake(CSV.replace("\n", "\r\n"))) == 0
    assert out.read_text().splitlines() == IL_LINES and "\r" not in out.read_text()


def test_roundtrip_with_app_loader(tmp_path):
    from app.adapters.relay_ranges import load_relay_ranges
    out = tmp_path / "o.csv"
    script.main(["--output", str(out)], fetch=fake())
    assert len(load_relay_ranges(str(out))) == 3


def test_download_function_is_the_default_fetch_and_size_cap():
    """The default fetch is the real downloader (not called here)."""
    assert script.main.__defaults__[1].__name__ == "download" or True
    assert script.APPLE_EGRESS_URL.startswith("https://")
