"""NetworkPolicy on a temporary DB; documentation IP ranges only."""
import pytest

from app.db import Database
from app.errors import InvalidNetworkRangeError, OffCampusError
from app.repositories.settings import SettingsRepository
from app.services.network import NetworkPolicy


@pytest.fixture
def settings(tmp_path) -> SettingsRepository:
    db = Database(str(tmp_path / "n.db"))
    db.init_schema()
    return SettingsRepository(db)


@pytest.fixture
def policy(settings) -> NetworkPolicy:
    p = NetworkPolicy(settings)
    p.save_ranges(["192.0.2.0/24", "2001:db8::/32"])
    return p


@pytest.mark.parametrize(
    "peer, cf, expected",
    [
        ("127.0.0.1", "192.0.2.10", "192.0.2.10"),
        ("::1", "2001:db8::5", "2001:db8::5"),
        ("::ffff:127.0.0.1", "192.0.2.10", "192.0.2.10"),
        ("127.0.0.1", None, "127.0.0.1"),
        ("198.51.100.7", "192.0.2.10", "198.51.100.7"),
        ("192.0.2.20", None, "192.0.2.20"),
        ("127.0.0.1", "::ffff:192.0.2.10", "192.0.2.10"),
    ],
)
def test_resolve_client_ip(peer, cf, expected):
    assert NetworkPolicy.resolve_client_ip(peer, cf) == expected


def test_resolve_malformed_values_fail_closed(policy):
    assert NetworkPolicy.resolve_client_ip("garbage", "192.0.2.10") == "garbage"
    with pytest.raises(OffCampusError):
        policy.ensure_allowed(NetworkPolicy.resolve_client_ip("127.0.0.1", "not-an-ip"))


@pytest.mark.parametrize("ip", ["192.0.2.0", "192.0.2.255", "2001:db8::1", "::ffff:192.0.2.10"])
def test_allowed(policy, ip):
    policy.ensure_allowed(ip)


@pytest.mark.parametrize("ip", ["192.0.1.255", "192.0.3.0", "2001:db9::1", "not-an-ip", ""])
def test_refused(policy, ip):
    with pytest.raises(OffCampusError) as err:
        policy.ensure_allowed(ip)
    assert err.value.user_message.startswith("Check-in only works on the university Wi-Fi")


def test_ipv4_against_ipv6_only_list(settings):
    p = NetworkPolicy(settings)
    p.save_ranges(["2001:db8::/32"])
    with pytest.raises(OffCampusError):
        p.ensure_allowed("192.0.2.10")


def test_empty_list_refuses_everyone(settings):
    with pytest.raises(OffCampusError):
        NetworkPolicy(settings).ensure_allowed("192.0.2.10")


def test_edit_used_at_once(policy):
    policy.save_ranges(["198.51.100.0/24"])
    policy.ensure_allowed("198.51.100.9")
    with pytest.raises(OffCampusError):
        policy.ensure_allowed("192.0.2.10")


def test_save_normalises_and_drops_blanks(policy):
    policy.save_ranges(["192.0.2.1/24", "", "  ", "2001:db8::/32", "192.0.2.7"])
    assert policy.ranges() == ["192.0.2.0/24", "2001:db8::/32", "192.0.2.7/32"]


@pytest.mark.parametrize("bad", ["300.1.1.1/24", "192.0.2.0/33", "hello"])
def test_invalid_line_keeps_list(policy, bad):
    before = policy.ranges()
    with pytest.raises(InvalidNetworkRangeError) as err:
        policy.save_ranges(["198.51.100.0/24", bad])
    assert err.value.user_message == "This is not a valid network range (e.g. 192.0.2.0/24)."
    assert policy.ranges() == before


def test_client_ip_never_reaches_repository(policy, settings, monkeypatch):
    seen = []
    original = settings.list_values
    monkeypatch.setattr(settings, "list_values", lambda *a: seen.append(a) or original(*a))
    policy.ensure_allowed("192.0.2.10")
    assert seen == [("campus_range",)]
