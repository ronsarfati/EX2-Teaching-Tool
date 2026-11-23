"""Network origin of a client (FR-1.2-FR-1.4, FR-1.19, D13, D21, D30, D32): campus, Apple relay or off campus."""
from __future__ import annotations

import ipaddress
from typing import Optional, Sequence

from app.adapters.relay_ranges import IPNetwork
from app.errors import InvalidNetworkRangeError, OffCampusError
from app.repositories.checkins import NetworkOrigin
from app.repositories.settings import SettingsRepository

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _parse(text: str) -> Optional[IPAddress]:
    """Parse an address, turning IPv4-mapped IPv6 into IPv4; None if malformed."""
    try:
        address = ipaddress.ip_address(text.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


class NetworkPolicy:
    SETTING_KIND = "campus_range"

    def __init__(self, settings: SettingsRepository, relay_ranges: Sequence[IPNetwork] = ()) -> None:
        self._settings = settings
        self._relay_ranges = tuple(relay_ranges)  # read-only after start-up; empty = relay list not loaded

    @staticmethod
    def resolve_client_ip(peer: str, cf_connecting_ip: Optional[str]) -> str:
        """Trust CF-Connecting-IP only when the socket peer is loopback (the local cloudflared).

        Any other peer could forge the header, so its own address is used. Malformed values are returned
        unchanged: classify then refuses them (fail closed).
        """
        peer_ip = _parse(peer)
        if peer_ip is not None and peer_ip.is_loopback and cf_connecting_ip:
            forwarded = _parse(cf_connecting_ip)
            return str(forwarded) if forwarded is not None else cf_connecting_ip
        return str(peer_ip) if peer_ip is not None else peer

    def classify(self, client_ip: str) -> NetworkOrigin:
        """Tell where client_ip comes from. Campus ranges are read at every call (FR-1.4).

        Refuses (OffCampusError) only an unconfigured app (empty campus list, fail closed) or a malformed
        address; any other network is accepted and labelled (D32). The address is only compared, never
        stored or logged (D21).
        """
        campus = [ipaddress.ip_network(text) for text in self.ranges()]
        if not campus:
            raise OffCampusError()
        address = _parse(client_ip)
        if address is None:
            raise OffCampusError()
        if self._contains(campus, address):
            return NetworkOrigin.CAMPUS  # campus wins when a range is in both lists
        if self._contains(self._relay_ranges, address):
            return NetworkOrigin.APPLE_RELAY
        return NetworkOrigin.OFF_CAMPUS

    def ensure_allowed(self, client_ip: str) -> None:
        """Refuse early (unconfigured app, malformed address) when the origin itself is not needed."""
        self.classify(client_ip)

    def relay_range_count(self) -> int:
        """Number of Apple relay ranges loaded; 0 means "not loaded"."""
        return len(self._relay_ranges)

    @staticmethod
    def _contains(networks: Sequence[IPNetwork], address: IPAddress) -> bool:
        # Compare versions explicitly so an IPv4 address never meets an IPv6 range.
        return any(address.version == network.version and address in network for network in networks)

    def ranges(self) -> list[str]:
        return self._settings.list_values(self.SETTING_KIND)

    def save_ranges(self, lines: list[str]) -> None:
        """Validate every non-blank line first; any invalid one raises and leaves the stored list unchanged."""
        normalised: list[str] = []
        for line in lines:
            text = line.strip()
            if not text:
                continue
            try:
                normalised.append(str(ipaddress.ip_network(text, strict=False)))
            except ValueError:
                raise InvalidNetworkRangeError() from None
        self._settings.replace_values(self.SETTING_KIND, normalised)
