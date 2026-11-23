"""Extra NetworkPolicy tests: CIDR edges, header trust, save_ranges input hygiene, privacy. Covers FR-1.2-FR-1.4, D21, D30, D31."""
import logging

import pytest

from app.db import Database
from app.errors import InvalidNetworkRangeError, OffCampusError
from app.repositories.settings import SettingsRepository
from app.services.network import NetworkPolicy


@pytest.fixture
def settings(tmp_path) -> SettingsRepository:
    db = Database(str(tmp_path / "x.db"))
    db.init_schema()
    return SettingsRepository(db)


@pytest.fixture
def policy(settings) -> NetworkPolicy:
    return NetworkPolicy(settings)


def _allowed(policy, ip) -> bool:
    try:
        policy.ensure_allowed(ip)
    except OffCampusError:
        return False
    return True


# ---- CIDR edges (Covers FR-1.2) ----
def test_ipv4_slash32_matches_only_that_host(policy):
    policy.save_ranges(["192.0.2.7/32"])
    assert _allowed(policy, "192.0.2.7")
    assert not _allowed(policy, "192.0.2.6")
    assert not _allowed(policy, "192.0.2.8")


def test_ipv4_slash0_allows_every_ipv4_but_no_ipv6(policy):
    policy.save_ranges(["0.0.0.0/0"])
    assert _allowed(policy, "0.0.0.0")
    assert _allowed(policy, "255.255.255.255")
    assert _allowed(policy, "192.0.2.1")
    assert not _allowed(policy, "2001:db8::1")


def test_ipv6_slash128_matches_only_that_host(policy):
    policy.save_ranges(["2001:db8::7/128"])
    assert _allowed(policy, "2001:db8::7")
    assert not _allowed(policy, "2001:db8::6")
    assert not _allowed(policy, "2001:db8::8")


def test_ipv6_slash64_first_last_and_outside(policy):
    policy.save_ranges(["2001:db8:0:1::/64"])
    assert _allowed(policy, "2001:db8:0:1::")
    assert _allowed(policy, "2001:db8:0:1:ffff:ffff:ffff:ffff")
    assert not _allowed(policy, "2001:db8:0:0:ffff:ffff:ffff:ffff")
    assert not _allowed(policy, "2001:db8:0:2::")


@pytest.mark.parametrize(
    "cidr, inside, outside",
    [
        ("10.1.2.0/25", ["10.1.2.0", "10.1.2.127"], ["10.1.1.255", "10.1.2.128"]),
        ("10.1.2.128/25", ["10.1.2.128", "10.1.2.255"], ["10.1.2.127", "10.1.3.0"]),
        ("172.16.0.0/12", ["172.16.0.0", "172.31.255.255"], ["172.15.255.255", "172.32.0.0"]),
    ],
)
def test_cidr_first_last_inside_and_just_outside(policy, cidr, inside, outside):
    policy.save_ranges([cidr])
    assert all(_allowed(policy, ip) for ip in inside)
    assert not any(_allowed(policy, ip) for ip in outside)


def test_ipv4_client_vs_ipv6_only_list_refused(policy):
    policy.save_ranges(["::/0"])
    assert not _allowed(policy, "192.0.2.1")
    assert _allowed(policy, "2001:db8::1")


def test_ipv4_mapped_client_against_ipv4_range(policy):
    policy.save_ranges(["192.0.2.0/24"])
    assert _allowed(policy, "::ffff:192.0.2.200")
    assert not _allowed(policy, "::ffff:192.0.3.1")


# ---- Header trust (Covers FR-1.3, D30, D31) ----
@pytest.mark.parametrize("peer", ["::ffff:127.0.0.1", "127.0.0.1", "::1", "127.5.5.5"])
def test_loopback_peer_variants_trust_header(peer):
    assert NetworkPolicy.resolve_client_ip(peer, "192.0.2.10") == "192.0.2.10"


@pytest.mark.parametrize("peer", ["198.51.100.7", "2001:db8::9", "::ffff:198.51.100.7", "10.0.0.1"])
def test_spoofed_header_from_non_loopback_ignored(peer, policy):
    policy.save_ranges(["192.0.2.0/24"])
    resolved = NetworkPolicy.resolve_client_ip(peer, "192.0.2.10")
    assert resolved != "192.0.2.10"
    with pytest.raises(OffCampusError):
        policy.ensure_allowed(resolved)


def test_empty_header_from_loopback_uses_peer():
    assert NetworkPolicy.resolve_client_ip("127.0.0.1", "") == "127.0.0.1"


@pytest.mark.parametrize("header", ["192.0.2.10, 203.0.113.5", "203.0.113.5,192.0.2.10", "192.0.2.10,"])
def test_multi_value_header_refused_fail_closed(policy, header):
    """Design is silent on comma-separated headers; observed behaviour is fail closed (reported as spec gap)."""
    policy.save_ranges(["192.0.2.0/24"])
    resolved = NetworkPolicy.resolve_client_ip("127.0.0.1", header)
    with pytest.raises(OffCampusError):
        policy.ensure_allowed(resolved)


def test_header_whitespace_is_tolerated():
    assert NetworkPolicy.resolve_client_ip("127.0.0.1", "  192.0.2.10 ") == "192.0.2.10"


# ---- save_ranges input (Covers FR-1.4) ----
def test_whitespace_and_blank_lines(policy):
    policy.save_ranges(["  192.0.2.0/24  ", "\t", "", "\n", " 2001:db8::/32\n"])
    assert policy.ranges() == ["192.0.2.0/24", "2001:db8::/32"]


def test_all_blank_lines_empties_list_and_refuses_all(policy):
    policy.save_ranges(["192.0.2.0/24"])
    policy.save_ranges(["", "  "])
    assert policy.ranges() == []
    assert not _allowed(policy, "192.0.2.10")


def test_comment_line_is_invalid(policy):
    """Design does not define comments; observed: '# ...' is an invalid range (reported as spec gap)."""
    policy.save_ranges(["192.0.2.0/24"])
    with pytest.raises(InvalidNetworkRangeError):
        policy.save_ranges(["# campus wifi", "198.51.100.0/24"])
    assert policy.ranges() == ["192.0.2.0/24"]


@pytest.mark.parametrize("bad_pos", [0, 1, 2])
def test_mixed_valid_invalid_leaves_list_unchanged(policy, bad_pos):
    policy.save_ranges(["192.0.2.0/24"])
    lines = ["198.51.100.0/24", "203.0.113.0/24"]
    lines.insert(bad_pos, "999.0.0.0/8")
    with pytest.raises(InvalidNetworkRangeError):
        policy.save_ranges(lines)
    assert policy.ranges() == ["192.0.2.0/24"]
    assert _allowed(policy, "192.0.2.5")
    assert not _allowed(policy, "198.51.100.5")


def test_host_bits_set_normalised_non_strict(policy):
    """Design: strict=False, so 10.0.0.5/24 is accepted and stored as 10.0.0.0/24."""
    policy.save_ranges(["10.0.0.5/24", "2001:db8::1/64"])
    assert policy.ranges() == ["10.0.0.0/24", "2001:db8::/64"]
    assert _allowed(policy, "10.0.0.200")


@pytest.mark.parametrize("bad", ["10.0.0.0/24/8", "10.0.0.0/-1", "10.0.0.0/", "1.2.3", "2001:db8::/129", "10.0.0.0 /24"])
def test_more_invalid_inputs(policy, bad):
    with pytest.raises(InvalidNetworkRangeError):
        policy.save_ranges([bad])
    assert policy.ranges() == []


# ---- Privacy (Covers D21) ----
def test_client_ip_not_stored_or_logged(policy, settings, caplog):
    policy.save_ranges(["192.0.2.0/24"])
    client = "192.0.2.123"
    with caplog.at_level(logging.DEBUG):
        policy.ensure_allowed(client)
        with pytest.raises(OffCampusError):
            policy.ensure_allowed("203.0.113.77")
        NetworkPolicy.resolve_client_ip("127.0.0.1", client)
    assert client not in caplog.text and "203.0.113.77" not in caplog.text
    assert settings.list_values("campus_range") == ["192.0.2.0/24"]
    import sqlite3
    db_file = settings._db.path if hasattr(settings._db, "path") else None
    if db_file:
        raw = open(db_file, "rb").read()
        assert b"192.0.2.123" not in raw and b"203.0.113.77" not in raw
