"""Tests for SSRF protection module."""

from __future__ import annotations

import logging

import pytest

from mattermost_summarizer.ssrf import (
    SSRFCheckResult,
    check_hostname_blocked,
    check_url_ssrf,
    ip_in_range,
    ipv6_in_range,
)


class TestIPInRange:
    def test_loopback_range(self) -> None:
        assert ip_in_range("127.0.0.1", "127.0.0.0/8") is True
        assert ip_in_range("127.255.255.255", "127.0.0.0/8") is True
        assert ip_in_range("127.0.0.0", "127.0.0.0/8") is True

    def test_rfc1918_10(self) -> None:
        assert ip_in_range("10.0.0.1", "10.0.0.0/8") is True
        assert ip_in_range("10.255.255.255", "10.0.0.0/8") is True
        assert ip_in_range("10.0.0.0", "10.0.0.0/8") is True

    def test_rfc1918_172(self) -> None:
        assert ip_in_range("172.16.0.1", "172.16.0.0/12") is True
        assert ip_in_range("172.31.255.255", "172.16.0.0/12") is True
        assert ip_in_range("172.20.4.5", "172.16.0.0/12") is True

    def test_rfc1918_192(self) -> None:
        assert ip_in_range("192.168.1.1", "192.168.0.0/16") is True
        assert ip_in_range("192.168.255.255", "192.168.0.0/16") is True

    def test_linklocal(self) -> None:
        assert ip_in_range("169.254.1.1", "169.254.0.0/16") is True
        assert ip_in_range("169.254.255.255", "169.254.0.0/16") is True

    def test_multicast(self) -> None:
        assert ip_in_range("224.0.0.1", "224.0.0.0/4") is True
        assert ip_in_range("239.255.255.255", "224.0.0.0/4") is True

    def test_current_network(self) -> None:
        assert ip_in_range("0.0.0.1", "0.0.0.0/8") is True

    def test_outside_range(self) -> None:
        assert ip_in_range("8.8.8.8", "10.0.0.0/8") is False
        assert ip_in_range("1.1.1.1", "127.0.0.0/8") is False
        assert ip_in_range("8.8.8.8", "192.168.0.0/16") is False

    def test_invalid_ip(self) -> None:
        assert ip_in_range("invalid", "10.0.0.0/8") is False
        assert ip_in_range("", "10.0.0.0/8") is False

    def test_invalid_cidr(self) -> None:
        assert ip_in_range("10.0.0.1", "invalid") is False


class TestIPv6InRange:
    def test_loopback(self) -> None:
        assert ipv6_in_range("::1", "::1/128") is True

    def test_ipv6_linklocal(self) -> None:
        assert ipv6_in_range("fe80::1", "fe80::/10") is True

    def test_ipv6_unique_local(self) -> None:
        assert ipv6_in_range("fc00::1", "fc00::/7") is True
        assert ipv6_in_range("fd00::1", "fc00::/7") is True

    def test_ipv6_multicast(self) -> None:
        assert ipv6_in_range("ff00::1", "ff00::/8") is True
        assert ipv6_in_range("ff02::1", "ff00::/8") is True

    def test_ipv6_outside_range(self) -> None:
        assert ipv6_in_range("2001:db8::1", "fc00::/7") is False
        assert ipv6_in_range("::1", "fe80::/10") is False

    def test_ipv6_invalid(self) -> None:
        assert ipv6_in_range("invalid", "::1/128") is False


class TestCheckHostnameBlocked:
    def test_blocked_tlds(self) -> None:
        assert check_hostname_blocked("myserver.local", [".local"]) == (True, "blocked hostname: .local")
        assert check_hostname_blocked("jira.internal", [".internal"]) == (True, "blocked hostname: .internal")
        assert check_hostname_blocked("server.corp", [".corp"]) == (True, "blocked hostname: .corp")
        assert check_hostname_blocked("db.internal.local", [".local"]) == (True, "blocked hostname: .local")
        assert check_hostname_blocked("github.com", [".github.com"]) == (True, "blocked hostname: .github.com")
        assert check_hostname_blocked("api.github.com", [".github.com"]) == (False, None)

    def test_allowed_hostnames(self) -> None:
        assert check_hostname_blocked("github.com", [".local"]) == (False, None)
        assert check_hostname_blocked("jira.company.com", [".local"]) == (False, None)
        assert check_hostname_blocked("localhost", [".internal"]) == (False, None)

    def test_case_insensitive(self) -> None:
        assert check_hostname_blocked("Server.Local", [".local"]) == (True, "blocked hostname: .local")
        assert check_hostname_blocked("GITHUB.COM", [".github.com"]) == (True, "blocked hostname: .github.com")


class TestCheckURLSSRF:
    def test_blocks_localhost(self) -> None:
        result = check_url_ssrf("http://localhost/server")
        assert result.is_safe is False
        assert ".local" in (result.reason or "")

    def test_blocks_loopback_ip(self) -> None:
        result = check_url_ssrf("http://127.0.0.1/server")
        assert result.is_safe is False
        assert "127.0.0.0/8" in (result.reason or "")

    def test_blocks_private_10(self) -> None:
        result = check_url_ssrf("http://10.0.0.1/api")
        assert result.is_safe is False
        assert "10.0.0.0/8" in (result.reason or "")

    def test_blocks_private_172(self) -> None:
        result = check_url_ssrf("http://172.20.4.5/api")
        assert result.is_safe is False
        assert "172.16.0.0/12" in (result.reason or "")

    def test_blocks_private_192(self) -> None:
        result = check_url_ssrf("http://192.168.1.100/endpoint")
        assert result.is_safe is False
        assert "192.168.0.0/16" in (result.reason or "")

    def test_blocks_linklocal(self) -> None:
        result = check_url_ssrf("http://169.254.169.254/latest/meta-data")
        assert result.is_safe is False
        assert "169.254.0.0/16" in (result.reason or "")

    def test_blocks_ipv6_loopback(self) -> None:
        result = check_url_ssrf("http://[::1]/server")
        assert result.is_safe is False

    def test_blocks_file_scheme(self) -> None:
        result = check_url_ssrf("file:///etc/passwd")
        assert result.is_safe is False
        assert "file" in (result.reason or "").lower()

    def test_blocks_data_scheme(self) -> None:
        result = check_url_ssrf("data:text/html,<script>alert(1)</script>")
        assert result.is_safe is False
        assert "data" in (result.reason or "").lower()

    def test_blocks_ftp_scheme(self) -> None:
        result = check_url_ssrf("ftp://files.example.com/data")
        assert result.is_safe is False
        assert "ftp" in (result.reason or "").lower()

    def test_allows_https_github(self) -> None:
        result = check_url_ssrf("https://github.com/canonical/mattermost-summarizer/issues/123")
        assert result.is_safe is True
        assert result.reason is None

    def test_allows_http_github(self) -> None:
        result = check_url_ssrf("http://github.com/canonical/mattermost-summarizer/issues/123")
        assert result.is_safe is True

    def test_allows_https_launchpad(self) -> None:
        result = check_url_ssrf("https://bugs.launchpad.net/ubuntu/+bug/123456")
        assert result.is_safe is True

    def test_blocks_internal_hostname(self) -> None:
        result = check_url_ssrf("https://jira.internal.company.com/browse/TICKET-1")
        assert result.is_safe is False
        assert ".internal" in (result.reason or "")

    def test_blocks_dotlocal(self) -> None:
        result = check_url_ssrf("http://db.myserver.local/api")
        assert result.is_safe is False

    def test_custom_blocked_ips(self) -> None:
        result = check_url_ssrf("http://192.168.1.1/", blocked_ips=["192.168.0.0/16"])
        assert result.is_safe is False

    def test_custom_blocked_ips_excludes_default(self) -> None:
        result = check_url_ssrf(
            "http://10.0.0.1/",
            blocked_ips=["192.168.0.0/16"],
        )
        assert result.is_safe is True

    def test_custom_blocked_hostnames(self) -> None:
        result = check_url_ssrf(
            "https://github.com/repo",
            blocked_hostnames=[".local", ".internal", ".github.com"],
        )
        assert result.is_safe is False
        assert "github.com" in (result.reason or "")

    def test_invalid_url(self) -> None:
        result = check_url_ssrf("not-a-valid-url")
        assert result.is_safe is False

    def test_no_scheme(self) -> None:
        result = check_url_ssrf("github.com/canonical/repo")
        assert result.is_safe is False


class TestSSRFLogging:
    def test_logs_blocked_attempts(self, caplog: pytest.CaptureFixture[str]) -> None:
        with caplog.at_level(logging.WARNING):
            check_url_ssrf("http://127.0.0.1/server", log_blocked=True)

        assert any("SSRF attempt blocked" in record.message for record in caplog.records)

    def test_no_log_when_disabled(self, caplog: pytest.CaptureFixture[str]) -> None:
        with caplog.at_level(logging.WARNING):
            check_url_ssrf("http://127.0.0.1/server", log_blocked=False)

        assert not any("SSRF attempt blocked" in record.message for record in caplog.records)


class TestSSRFCheckResult:
    def test_safe_result_fields(self) -> None:
        result = SSRFCheckResult(is_safe=True, reason=None, blocked_url="https://example.com")
        assert result.is_safe is True
        assert result.reason is None
        assert result.blocked_url == "https://example.com"

    def test_blocked_result_fields(self) -> None:
        result = SSRFCheckResult(
            is_safe=False,
            reason="private address 10.0.0.0/8",
            blocked_url="http://10.0.0.1/",
        )
        assert result.is_safe is False
        assert result.reason == "private address 10.0.0.0/8"
        assert result.blocked_url == "http://10.0.0.1/"


class TestEdgeCases:
    def test_url_with_port(self) -> None:
        result = check_url_ssrf("http://192.168.1.1:8080/api")
        assert result.is_safe is False

    def test_url_with_ipv6_address_and_port(self) -> None:
        result = check_url_ssrf("http://[fe80::1]:8080/api")
        assert result.is_safe is False

    def test_url_path_preserved(self) -> None:
        result = check_url_ssrf("http://192.168.1.1/api/v1/users?token=secret")
        assert result.is_safe is False

    def test_https_urls_with_port(self) -> None:
        result = check_url_ssrf("https://github.com:443/canonical/repo")
        assert result.is_safe is True

    def test_http_url_with_path(self) -> None:
        result = check_url_ssrf("http://myserver.local/api/data")
        assert result.is_safe is False

    def test_multiple_blocked_tlds(self) -> None:
        result = check_url_ssrf(
            "https://jira.corp.internal.company.com",
            blocked_hostnames=[".local", ".internal", ".corp"],
        )
        assert result.is_safe is False
