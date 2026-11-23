"""Download Apple's iCloud Private Relay egress ranges and keep one country (FR-1.19, D32).

Run by hand before class (the app never downloads anything):
    python scripts/update_relay_ranges.py [--country IL] [--output data/apple_relay_ranges_IL.csv]
The output is git-ignored; the app reads it at start-up (RELAY_RANGES_PATH).
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # like seed_demo.py: reuse the app's parser

from app.adapters.relay_ranges import parse_egress_csv  # noqa: E402

APPLE_EGRESS_URL = "https://mask-api.icloud.com/egress-ip-ranges.csv"
TIMEOUT_SECONDS = 60
MAX_BYTES = 50 * 1024 * 1024  # the real file is about 12 MB; the cap protects against a runaway response


def download(url: str) -> str:
    """Fetch the CSV text. The only network code of the project's tooling; tests inject a fake instead."""
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (constant https URL)
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise OSError("response larger than the allowed maximum")
    return data.decode("utf-8")


def _write_atomically(output: Path, lines: list[str]) -> None:
    """Write to a temporary file then rename, so a failure never leaves a half-written list."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)  # only still there if the write or the rename failed


def main(argv: Optional[list[str]] = None, fetch: Callable[[str], str] = download) -> int:
    """Return 0 on success, 1 on any failure (the existing output file is then left untouched)."""
    parser = argparse.ArgumentParser(description="Update the Apple Private Relay range list.")
    parser.add_argument("--country", default="IL", help="two-letter country code to keep (default IL)")
    parser.add_argument("--output", help="output file (default data/apple_relay_ranges_<COUNTRY>.csv)")
    args = parser.parse_args(argv)
    country = args.country.strip().upper()
    output = Path(args.output or f"data/apple_relay_ranges_{country}.csv")

    try:
        text = fetch(APPLE_EGRESS_URL)
    except (OSError, UnicodeDecodeError) as error:  # URLError and TimeoutError are OSError subclasses
        print(f"Download failed: {error}", file=sys.stderr)
        return 1
    parsed = parse_egress_csv(text.splitlines(), country)
    if not parsed.kept_lines:
        print(f"No range found for country {country}; {output} left untouched.", file=sys.stderr)
        return 1
    _write_atomically(output, parsed.kept_lines)
    v4 = sum(1 for network in parsed.networks if isinstance(network, ipaddress.IPv4Network))
    print(f"{len(parsed.networks)} ranges for {country} ({v4} IPv4, {len(parsed.networks) - v4} IPv6), "
          f"{parsed.skipped} malformed lines skipped -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
