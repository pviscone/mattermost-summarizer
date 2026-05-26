"""SSRF protection module for blocking unsafe URLs.

Provides URL safety checking to prevent Server-Side Request Forgery attacks
when following external references (GitHub, Launchpad, Mattermost threads).

Blocked:
- Private IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, etc.)
- IPv6 private ranges (::1, fc00::/7, fe80::/10, ff00::/8)
- Internal hostnames (.local, .localhost, .internal, .corp, etc.)
- Non-HTTP(S) URL schemes (file://, data:, ftp://, etc.)
"""

from __future__ import annotations

import ipaddress
import logging
import re
from dataclasses import dataclass

__all__ = [
    "SSRFCheckResult",
    "check_url_ssrf",
    "ip_in_range",
    "ipv6_in_range",
    "check_hostname_blocked",
    "DEFAULT_BLOCKED_IPS",
    "DEFAULT_BLOCKED_IPV6_RANGES",
    "DEFAULT_BLOCKED_HOSTNAMES",
    "DEFAULT_ALLOWED_SCHEMES",
]

logger = logging.getLogger(__name__)

DEFAULT_BLOCKED_IPS: list[str] = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "224.0.0.0/4",
    "0.0.0.0/8",
]

DEFAULT_BLOCKED_IPV6_RANGES: list[str] = [
    "::1/128",
    "fc00::/7",
    "fe80::/10",
    "ff00::/8",
]

DEFAULT_BLOCKED_HOSTNAMES: list[str] = [
    ".local",
    ".localhost",
    ".internal",
    ".corp",
    ".intranet",
    ".private",
    ".example",
    ".test",
    ".invalid",
    ".mail",
]

DEFAULT_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

_ssrf_blocked_ips: list[str] | None = None
_ssrf_blocked_hostnames: list[str] | None = None
_ssrf_log_blocked: bool = True


def set_ssrf_defaults(
    blocked_ips: list[str] | None,
    blocked_hostnames: list[str] | None,
    log_blocked: bool,
) -> None:
    """Set module-level SSRF defaults from config.

    Args:
        blocked_ips: List of blocked IP CIDRs (None = use DEFAULT_BLOCKED_IPS)
        blocked_hostnames: List of blocked hostname patterns (None = use DEFAULT_BLOCKED_HOSTNAMES)
        log_blocked: Whether to log blocked attempts
    """
    global _ssrf_blocked_ips, _ssrf_blocked_hostnames, _ssrf_log_blocked
    _ssrf_blocked_ips = blocked_ips
    _ssrf_blocked_hostnames = blocked_hostnames
    _ssrf_log_blocked = log_blocked


def get_ssrf_defaults() -> tuple[list[str] | None, list[str] | None, bool]:
    """Get current module-level SSRF defaults.

    Returns:
        Tuple of (blocked_ips, blocked_hostnames, log_blocked)
    """
    return (_ssrf_blocked_ips, _ssrf_blocked_hostnames, _ssrf_log_blocked)


@dataclass
class SSRFCheckResult:
    """Result of an SSRF safety check."""

    is_safe: bool
    reason: str | None = None
    blocked_url: str = ""


def ip_in_range(ip: str, cidr: str) -> bool:
    """Check if an IPv4 address is within a CIDR range.

    Args:
        ip: IPv4 address string (e.g., "192.168.1.1")
        cidr: CIDR notation (e.g., "192.168.0.0/16")

    Returns:
        True if ip is within the cidr range
    """
    try:
        ip_addr = ipaddress.IPv4Address(ip)
        network = ipaddress.IPv4Network(cidr, strict=False)
        return ip_addr in network
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return False


def ipv6_in_range(ip: str, cidr: str) -> bool:
    """Check if an IPv6 address is within a CIDR range.

    Args:
        ip: IPv6 address string (e.g., "::1" or "fe80::1")
        cidr: CIDR notation (e.g., "fe80::/10")

    Returns:
        True if ip is within the cidr range
    """
    try:
        ip_addr = ipaddress.IPv6Address(ip)
        network = ipaddress.IPv6Network(cidr, strict=False)
        return ip_addr in network
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return False


def _parse_hostname_from_url(url: str) -> str | None:
    """Extract hostname from a URL.

    Args:
        url: URL string to parse

    Returns:
        Hostname string or None if parsing fails
    """
    match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/]+)", url)
    if match:
        host_part = match.group(1)
        if host_part.startswith("["):
            bracket_end = host_part.find("]")
            if bracket_end > 0:
                return host_part[1:bracket_end]
        colon_idx = host_part.find(":")
        if colon_idx > 0:
            return host_part[:colon_idx]
        return host_part
    return None


def check_hostname_blocked(hostname: str, blocked_tlds: list[str]) -> tuple[bool, str | None]:
    """Check if a hostname matches any blocked pattern.

    Args:
        hostname: Hostname to check
        blocked_tlds: List of blocked TLDs/hostnames (e.g., [".local", ".internal", ".github.com"])

    Returns:
        Tuple of (is_blocked, reason)

    Note:
        Patterns starting with "." are treated as suffix patterns:
        - Single-label suffixes (e.g., ".local", ".internal", ".corp"): block any hostname
          where that label appears as a component, e.g., "anything.local", "myserver.internal",
          "jira.internal.company.com" (contains "internal" as a label)
        - Multi-label suffixes (e.g., ".github.com"): block only exact domain matches,
          e.g., "github.com" matches but "api.github.com" does NOT
        Patterns without a leading "." match exact hostname (e.g., "localhost")
    """
    hostname_lower = hostname.lower()
    parts = hostname_lower.split(".")
    for blocked in blocked_tlds:
        blocked_lower = blocked.lower()
        if blocked_lower.startswith("."):
            suffix = blocked_lower[1:]
            suffix_parts = suffix.split(".")
            if len(suffix_parts) > 1:
                if hostname_lower == suffix:
                    return True, f"blocked hostname: {blocked}"
            else:
                if hostname_lower.endswith(f".{suffix}") or hostname_lower == suffix or suffix in parts:
                    return True, f"blocked hostname: {blocked}"
        elif hostname_lower == blocked_lower:
            return True, f"blocked hostname: {blocked}"
    return False, None


def check_url_ssrf(
    url: str,
    blocked_ips: list[str] | None = None,
    blocked_hostnames: list[str] | None = None,
    log_blocked: bool | None = None,
) -> SSRFCheckResult:
    """Check if a URL is safe to follow (no SSRF risk).

    Args:
        url: URL to check
        blocked_ips: Custom list of blocked IP CIDRs (None for defaults)
        blocked_hostnames: Custom list of blocked hostnames/TLDs (None for defaults)
        log_blocked: Whether to log blocked URL attempts (None = use module default)

    Returns:
        SSRFCheckResult with is_safe, reason, and blocked_url
    """
    ips_to_block = blocked_ips if blocked_ips is not None else (_ssrf_blocked_ips or DEFAULT_BLOCKED_IPS)
    hostnames_to_block = (
        blocked_hostnames if blocked_hostnames is not None else (_ssrf_blocked_hostnames or DEFAULT_BLOCKED_HOSTNAMES)
    )
    should_log = log_blocked if log_blocked is not None else _ssrf_log_blocked

    url = url.strip()

    match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", url)
    if not match:
        result = SSRFCheckResult(is_safe=False, reason="invalid URL format", blocked_url=url)
        if should_log:
            _log_blocked(url, "invalid URL format")
        return result

    scheme = match.group(1).lower()
    if scheme not in DEFAULT_ALLOWED_SCHEMES:
        result = SSRFCheckResult(
            is_safe=False,
            reason=f"URL scheme '{scheme}' is not allowed",
            blocked_url=url,
        )
        if should_log:
            _log_blocked(url, f"disallowed scheme: {scheme}")
        return result

    hostname = _parse_hostname_from_url(url)
    if not hostname:
        result = SSRFCheckResult(is_safe=False, reason="could not parse hostname", blocked_url=url)
        if should_log:
            _log_blocked(url, "could not parse hostname")
        return result

    is_blocked, block_reason = check_hostname_blocked(hostname, hostnames_to_block)
    if is_blocked:
        result = SSRFCheckResult(is_safe=False, reason=block_reason, blocked_url=url)
        if should_log:
            _log_blocked(url, block_reason or "blocked hostname")
        return result

    try:
        if ":" in hostname and not hostname.startswith("["):
            try:
                ipaddress.IPv6Address(hostname)
                is_ipv6 = True
            except ipaddress.AddressValueError:
                is_ipv6 = False
        elif hostname.startswith("[") and "]" in hostname:
            is_ipv6 = True
        else:
            is_ipv6 = False
    except ipaddress.AddressValueError:
        is_ipv6 = False

    if is_ipv6:
        try:
            ip_addr = ipaddress.IPv6Address(hostname)
            for cidr in DEFAULT_BLOCKED_IPV6_RANGES:
                if ipv6_in_range(str(ip_addr), cidr):
                    result = SSRFCheckResult(
                        is_safe=False,
                        reason=f"IPv6 {cidr}",
                        blocked_url=url,
                    )
                    if should_log:
                        _log_blocked(url, f"IPv6 blocked range: {cidr}")
                    return result
        except ipaddress.AddressValueError:
            pass
    else:
        for cidr in ips_to_block:
            if ip_in_range(hostname, cidr):
                result = SSRFCheckResult(
                    is_safe=False,
                    reason=f"private address {cidr}",
                    blocked_url=url,
                )
                if should_log:
                    _log_blocked(url, f"private IP range: {cidr}")
                return result

    return SSRFCheckResult(is_safe=True, reason=None, blocked_url=url)


def _log_blocked(url: str, reason: str) -> None:
    """Log a blocked SSRF attempt.

    Args:
        url: The blocked URL
        reason: Why it was blocked
    """
    logger.warning("SSRF attempt blocked: %s (%s)", url, reason)
