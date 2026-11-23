"""scripts/update_relay_ranges.py with an injected download: the network is never touched."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "update_relay_ranges.py"
spec = importlib.util.spec_from_file_location("update_relay_ranges", SCRIPT)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

CSV = "198.51.100.0/25,IL,IL-01,Tel Aviv,\n2001:db8:4000::/64,IL,IL-01,Tel Aviv,\n192.0.2.0/24,FR,FR-75,Paris,\nbad\n"


def test_writes_only_valid_lines_of_the_country(tmp_path, capsys):
    out = tmp_path / "sub" / "il.csv"  # parent is created
    assert script.main(["--output", str(out)], fetch=lambda url: CSV) == 0
    assert out.read_text().splitlines() == CSV.splitlines()[:2]
    assert "2 ranges for IL (1 IPv4, 1 IPv6), 1 malformed" in capsys.readouterr().out
    assert not list(out.parent.glob("*.tmp"))


def test_other_country(tmp_path):
    out = tmp_path / "fr.csv"
    assert script.main(["--country", "fr", "--output", str(out)], fetch=lambda url: CSV) == 0
    assert out.read_text().splitlines() == [CSV.splitlines()[2]]


@pytest.mark.parametrize("error", [OSError("down"), TimeoutError()])
def test_failure_leaves_existing_file_untouched(tmp_path, error):
    out = tmp_path / "il.csv"
    out.write_bytes(b"old\n")

    def failing(url):
        raise error

    assert script.main(["--output", str(out)], fetch=failing) == 1
    assert script.main(["--country", "DE", "--output", str(out)], fetch=lambda url: CSV) == 1  # no line for DE
    assert out.read_bytes() == b"old\n"
    assert not list(tmp_path.glob("*.tmp"))
