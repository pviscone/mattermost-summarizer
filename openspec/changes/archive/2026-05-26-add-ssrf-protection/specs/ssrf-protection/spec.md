# Spec: SSRF Protection

## Capability

Block URLs that resolve to private, loopback, link-local, or multicast IP addresses, or use internal/private hostnames, preventing Server-Side Request Forgery attacks during reference following.

## Requirements

### Requirement: SSRF check function
The system SHALL provide a `check_url_ssrf(url: str) -> SSRFCheckResult` function that determines if a URL is safe to follow.

The function SHALL return an `SSRFCheckResult` with:
- `is_safe: bool` — True if the URL is safe to follow
- `reason: str | None` — Human-readable reason if blocked, None if safe
- `blocked_url: str` — The URL that was blocked (same as input if blocked)

#### Scenario: Check blocks loopback IP
- **WHEN** `check_url_ssrf("http://127.0.0.1/server")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"loopback address 127.0.0.0/8"`

#### Scenario: Check blocks RFC 1918 private IP
- **WHEN** `check_url_ssrf("https://10.0.0.1/api/data")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"private address 10.0.0.0/8"`

#### Scenario: Check blocks private hostname
- **WHEN** `check_url_ssrf("https://jira.internal.company.com/browse/TICKET-1")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"blocked hostname: .internal"`

#### Scenario: Check blocks .local TLD
- **WHEN** `check_url_ssrf("http://myserver.local/api")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"blocked hostname: .local"`

#### Scenario: Check blocks file scheme
- **WHEN** `check_url_ssrf("file:///etc/passwd")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"URL scheme 'file' is not allowed"`

#### Scenario: Check allows safe external URL
- **WHEN** `check_url_ssrf("https://github.com/canonical/mattermost-summarizer/issues/123")` is called
- **THEN** `result.is_safe` is `True`
- **THEN** `result.reason` is `None`

### Requirement: Blocked IP ranges
The SSRF check SHALL reject URLs whose parsed IP (after resolution) falls within these IPv4 ranges:

| Range | Purpose |
|-------|---------|
| `127.0.0.0/8` | Loopback |
| `10.0.0.0/8` | RFC 1918 private |
| `172.16.0.0/12` | RFC 1918 private |
| `192.168.0.0/16` | RFC 1918 private |
| `169.254.0.0/16` | Link-local |
| `224.0.0.0/4` | Multicast |
| `0.0.0.0/8` | Current network |

#### Scenario: Blocks 192.168.x.x
- **WHEN** `check_url_ssrf("http://192.168.1.100/endpoint")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"private address 192.168.0.0/16"`

#### Scenario: Blocks 172.16-31.x.x
- **WHEN** `check_url_ssrf("http://172.20.4.5/api")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"private address 172.16.0.0/12"`

### Requirement: Blocked IPv6 ranges
The SSRF check SHALL reject URLs whose parsed IPv6 address falls within these ranges:

| Range | Purpose |
|-------|---------|
| `::1` | Loopback |
| `fc00::/7` | Unique local |
| `fe80::/10` | Link-local |
| `ff00::/8` | Multicast |

#### Scenario: Blocks IPv6 loopback
- **WHEN** `check_url_ssrf("http://[::1]/server")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"loopback address ::1"`

### Requirement: Blocked hostnames and TLDs
The SSRF check SHALL reject URLs whose hostname matches or ends with these patterns:
- `.local`
- `.localhost`
- `.internal`
- `.corp`
- `.intranet`
- `.private`
- `.example`
- `.test`
- `.invalid`
- `.mail`

#### Scenario: Blocks .localhost TLD
- **WHEN** `check_url_ssrf("https://db.internal.local/secret")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"blocked hostname: .local"`

#### Scenario: Blocks myserver.local
- **WHEN** `check_url_ssrf("http://myserver.local/api")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"blocked hostname: .local"`

### Requirement: Blocked URL schemes
Only `http` and `https` URL schemes are allowed. All other schemes SHALL be rejected.

#### Scenario: Blocks file scheme
- **WHEN** `check_url_ssrf("file:///etc/passwd")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"URL scheme 'file' is not allowed"`

#### Scenario: Blocks data scheme
- **WHEN** `check_url_ssrf("data:text/html,<script>alert(1)</script>")` is called
- **THEN** `result.is_safe` is `False`
- **THEN** `result.reason` is `"URL scheme 'data' is not allowed"`

#### Scenario: Allows http and https
- **WHEN** `check_url_ssrf("http://example.com")` is called
- **THEN** `result.is_safe` is `True`
- **WHEN** `check_url_ssrf("https://example.com")` is called
- **THEN** `result.is_safe` is `True`

### Requirement: Integration in URL classification
The SSRF check SHALL be called in `classify_url()` before returning the reference type.

- If `check_url_ssrf()` returns `is_safe=False`, the function SHALL return `ReferenceType.UNKNOWN`
- Blocked attempts SHALL be logged at WARNING level

#### Scenario: Unsafe URL returns UNKNOWN
- **WHEN** `classify_url("http://192.168.1.1/api")` is called
- **THEN** `check_url_ssrf` is called first
- **THEN** the function returns `ReferenceType.UNKNOWN`
- **THEN** a warning is logged with the blocked URL and reason

### Requirement: Defense-in-depth in fetch tools
The `FetchGitHubIssueExecutor` and `FetchLaunchpadBugExecutor` SHALL call `check_url_ssrf()` before attempting to fetch.

- If the URL is unsafe, the executor SHALL return a safe error observation
- The error message SHALL be human-readable but not reveal security details

#### Scenario: GitHub fetcher rejects SSRF URL
- **WHEN** `FetchGitHubIssueExecutor` receives a URL flagged as SSRF risk
- **THEN** it returns `FetchGitHubIssueObservation(error="URL is not accessible: <reason>")`
- **THEN** no HTTP request is made

### Requirement: Configurable blocklists
The `MattermostSummarizerConfig` SHALL support optional SSRF configuration:

- `ssrf_blocked_ips: list[str] | None` — Override default IP blocklist; None uses defaults
- `ssrf_blocked_hostnames: list[str] | None` — Override default hostname blocklist; None uses defaults
- `ssrf_log_blocked: bool` — Whether to log blocked attempts (default: True)

#### Scenario: Custom IP blocklist
- **WHEN** `ssrf_blocked_ips = ["10.0.0.0/8", "172.16.0.0/12"]` is configured
- **THEN** `192.168.0.0/16` is NOT blocked (only configured ranges are blocked)
- **THEN** `10.0.0.0/8` and `172.16.0.0/12` are blocked

#### Scenario: Disabling SSRF logging
- **WHEN** `ssrf_log_blocked = False` is configured
- **THEN** blocked URL attempts are not logged
- **THEN** `check_url_ssrf()` still returns correct results

### Requirement: Logging of blocked attempts
When `ssrf_log_blocked` is True (default), each blocked URL attempt SHALL be logged with:
- Timestamp
- Blocked URL
- Reason for blocking
- Reference type attempted (e.g., "GitHub issue", "Launchpad bug")

#### Scenario: Blocked attempt is logged
- **WHEN** `check_url_ssrf("http://localhost/server")` is called with logging enabled
- **THEN** a WARNING log is emitted with message containing "SSRF attempt blocked", the URL, and reason