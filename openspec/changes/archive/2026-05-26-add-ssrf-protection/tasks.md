# Tasks: Add SSRF Protection

## 1. Create ssrf.py Module

- [x] 1.1 Create `src/mattermost_summarizer/ssrf.py` with module docstring
- [x] 1.2 Define `SSRFCheckResult` dataclass with `is_safe`, `reason`, `blocked_url` fields
- [x] 1.3 Define default blocked IPv4 ranges as constants (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16, 224.0.0.0/4, 0.0.0.0/8)
- [x] 1.4 Define default blocked IPv6 ranges as constants (::1, fc00::/7, fe80::/10, ff00::/8)
- [x] 1.5 Define default blocked hostnames/TLDs as constants (.local, .localhost, .internal, .corp, .intranet, .private, .example, .test, .invalid, .mail)
- [x] 1.6 Implement `ip_in_range(ip: str, cidr: str) -> bool` helper for IPv4 CIDR checking
- [x] 1.7 Implement `ipv6_in_range(ip: str, cidr: str) -> bool` helper for IPv6 CIDR checking
- [x] 1.8 Implement `check_hostname_blocked(hostname: str, blocked_tlds: list[str]) -> tuple[bool, str | None]` function
- [x] 1.9 Implement `check_url_ssrf(url: str, blocked_ips: list[str] | None = None, blocked_hostnames: list[str] | None = None) -> SSRFCheckResult` main function
- [x] 1.10 Add logging for blocked attempts when `log_blocked=True`

## 2. Integrate SSRF Check in reference_tracker.py

- [x] 2.1 Import `check_url_ssrf` from `ssrf` module in `reference_tracker.py`
- [x] 2.2 Call `check_url_ssrf()` at the start of `classify_url()` function
- [x] 2.3 If URL is unsafe, log warning and return `ReferenceType.UNKNOWN`
- [x] 2.4 Run ruff and mypy to verify no type errors

## 3. Add Defense-in-Depth Checks in Fetch Tools

- [x] 3.1 In `fetch_github_issue/impl.py`: Import check_url_ssrf and call it in `__call__` before `_parse_url()`
- [x] 3.2 In `fetch_launchpad_bug/impl.py`: Import check_url_ssrf and call it in `__call__` before `_parse_bug_id()`
- [x] 3.3 Return safe error observations (don't expose security details) when URL is blocked
- [x] 3.4 Run ruff and mypy to verify no type errors

## 4. Add SSRF Configuration to config.py

- [x] 4.1 Add `ssrf_blocked_ips: list[str] | None = None` field to `MattermostSummarizerConfig`
- [x] 4.2 Add `ssrf_blocked_hostnames: list[str] | None = None` field to `MattermostSummarizerConfig`
- [x] 4.3 Add `ssrf_log_blocked: bool = True` field to `MattermostSummarizerConfig`
- [x] 4.4 Parse `[ssrf]` section from TOML config in `from_config()` method
- [x] 4.5 Add env var support (MM_SSRF_BLOCKED_IPS, MM_SSRF_BLOCKED_HOSTNAMES, MM_SSRF_LOG_BLOCKED)
- [x] 4.6 Run ruff and mypy to verify no type errors

## 5. Write Unit Tests for SSRF Module

- [x] 5.1 Create `tests/test_ssrf.py`
- [x] 5.2 Test `ip_in_range` with various IPv4 addresses
- [x] 5.3 Test `ipv6_in_range` with various IPv6 addresses
- [x] 5.4 Test loopback blocking (127.0.0.1, ::1)
- [x] 5.5 Test RFC 1918 private ranges (10.x, 172.16-31.x, 192.168.x)
- [x] 5.6 Test link-local blocking (169.254.x, fe80::)
- [x] 5.7 Test multicast blocking (224.x, ff00::)
- [x] 5.8 Test blocked hostname/TLD detection (.local, .localhost, .internal, .corp)
- [x] 5.9 Test blocked URL schemes (file://, data://, ftp://)
- [x] 5.10 Test allowed schemes (http://, https://)
- [x] 5.11 Test safe external URLs pass through
- [x] 5.12 Test logging behavior when logging is enabled
- [x] 5.13 Test custom config overrides (custom IP ranges, custom hostnames)

## 6. Integration Testing

- [x] 6.1 Run existing tests to ensure no regressions
- [x] 6.2 Run ruff linting: `uv run ruff check .`
- [x] 6.3 Run mypy type checking: `uv run mypy .`
- [x] 6.4 Test end-to-end with a mock internal URL to verify blocking works

## 7. Documentation

- [x] 7.1 Add SSRF configuration section to README (if exists) or document in config.py docstring
- [x] 7.2 Verify all new functions/modules have proper docstrings