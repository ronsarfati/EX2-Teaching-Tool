"""Apple iCloud Private Relay egress ranges (FR-1.19, D32): parser of Apple's CSV and start-up loader.

Shared by the app and scripts/update_relay_ranges.py so both read the same format. Apple's lines look like
`range,country,region,city,` (the range may be IPv4 or IPv6).
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedRanges:
    """Result of parsing: valid networks, their original lines, and how many malformed lines were skipped."""

    networks: list[IPNetwork]
    kept_lines: list[str]
    skipped: int


def parse_egress_csv(lines: Iterable[str], country: Optional[str]) -> ParsedRanges:
    """Keep the valid ranges of `country` (any country if None); count malformed lines in `skipped`.

    The country test comes before the range validation so only the wanted country is validated
    (a few hundred ranges instead of the ~285k of Apple's full file); other countries are not "skipped".
    """
    wanted = country.strip().upper() if country else None
    networks: list[IPNetwork] = []
    kept: list[str] = []
    skipped = 0
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        fields = line.split(",")
        if len(fields) < 2:
            skipped += 1
            continue
        if wanted is not None and fields[1].strip().upper() != wanted:
            continue
        try:
            networks.append(ipaddress.ip_network(fields[0].strip(), strict=False))
        except ValueError:
            skipped += 1
            continue
        kept.append(line)
    return ParsedRanges(networks, kept, skipped)


def load_relay_ranges(path: str) -> list[IPNetwork]:
    """Read the relay file written by the update script. Never raises: without the file the app still starts.

    Only counts and the path are logged, never a client address (D21).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            parsed = parse_egress_csv(handle, country=None)
    except (OSError, UnicodeDecodeError):
        logger.warning("Apple relay list not loaded: %s", path)
        return []
    logger.info("Apple relay list loaded: %d ranges (%d malformed lines skipped)", len(parsed.networks), parsed.skipped)
    return parsed.networks
