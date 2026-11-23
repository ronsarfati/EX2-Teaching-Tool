"""Campus-network filter (FR-1.2-FR-1.4, D13, D21, D30): accepts only clients inside lecturer-edited ranges."""
from __future__ import annotations

import ipaddress
from typing import Optional

from app.errors import InvalidNetworkRangeError, OffCampusError
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

    def __init__(self, settings: SettingsRepository) -> None:
        self._settings = settings

    @staticmethod
    def resolve_client_ip(peer: str, cf_connecting_ip: Optional[str]) -> str:
        """Trust CF-Connecting-IP only when the socket peer is loopback (the local cloudflared).

        Any other peer could forge the header, so its own address is used. Malformed values are returned
        unchanged: ensure_allowed then refuses them (fail closed).
        """
        peer_ip = _parse(peer)
        if peer_ip is not None and peer_ip.is_loopback and cf_connecting_ip:
            forwarded = _parse(cf_connecting_ip)
            return str(forwarded) if forwarded is not None else cf_connecting_ip
        return str(peer_ip) if peer_ip is not None else peer

    def ensure_allowed(self, client_ip: str) -> None:
        """Raise OffCampusError unless client_ip is in a stored range. Ranges are read at every call (FR-1.4).

        The address is only compared, never stored or logged (D21).
        """
        address = _parse(client_ip)
        if address is None:
            raise OffCampusError()
        for text in self.ranges():
            network = ipaddress.ip_network(text)
            # Compare versions explicitly so an IPv4 address never meets an IPv6 range.
            if address.version == network.version and address in network:
                return
        raise OffCampusError()

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
