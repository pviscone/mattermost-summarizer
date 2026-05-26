# Design: SSRF Protection

## Context

The system follows external URLs (GitHub, Launchpad, Mattermost threads) discovered in conversation content via sub-agent delegation. The `ReferenceTracker` prevents infinite recursion via depth limits, but does not restrict which hosts/IPs can be accessed. A malicious actor could provide internal network URLs as thread references, causing the system to make requests to internal services (SSRF attack).

Currently implemented:
- URL classification: Known patterns for GitHub, Launchpad, Mattermost
- Cycle detection: Per-URL tracking via `followed_urls`
- Depth limiting: Per-URL depth tracking with `max_depth`
- `sanitize_url()`: Handles IPv6 parsing edge cases only

## Goals / Non-Goals

**Goals:**
- Block URLs that resolve to private, loopback, link-local, or multicast IP ranges
- Block URLs with internal/private hostnames (.local, .internal, .corp, etc.)
- Block non-HTTP(S) URL schemes (file://, data:, etc.)
- Provide configurable blocklists with sensible defaults
- Log all blocked attempts for security auditing
- Apply to all external fetch tools (GitHub, Launchpad, Mattermost)

**Non-Goals:**
- DNS resolution-based blocking (hostname → IP check) — too complex/costly
- Allowlist mode (only permit known-good hosts) — too restrictive
- Blocking internal IP ranges in IP address form (e.g., `http://10.0.0.1/`) is handled but custom internal ranges are not configurable

## Decisions

### 1. Centralized SSRF Module + Per-Tool Defense

**Decision:** Create a new `ssrf.py` module with the blocking logic, integrate at URL classification level in `reference_tracker.py`, and add defense-in-depth checks in each fetch tool.

**Rationale:** The `reference_tracker.py` is the central choke point for URL classification — blocking there catches most SSRF attempts before they reach any tool. Per-tool checks provide defense in depth in case a URL bypasses classification or is passed directly to a tool. This follows the principle of layered security.

**Alternatives considered:**
- *Per-tool only*: Risk of missing URLs if classification is bypassed. Less maintainable as blocking logic would be duplicated.
- *Client-level only via httpx limits*: More robust but requires plumbing custom HTTP clients through all tools, more invasive change.

### 2. Default Blocked IP Ranges (IPv4 + IPv6)

**Decision:** Hard-code default blocked ranges:

| Range | Purpose |
|-------|---------|
| `127.0.0.0/8` | Loopback |
| `10.0.0.0/8` | RFC 1918 private |
| `172.16.0.0/12` | RFC 1918 private |
| `192.168.0.0/16` | RFC 1918 private |
| `169.254.0.0/16` | Link-local |
| `224.0.0.0/4` | Multicast |
| `::1` | IPv6 loopback |
| `fc00::/7` | IPv6 unique local |
| `fe80::/10` | IPv6 link-local |
| `ff00::/8` | IPv6 multicast |

**Rationale:** These cover the standard private/internal ranges. IPv6 is included because modern networks may have IPv6 connectivity.

### 3. Blocked Hostnames/TLDs

**Decision:** Block hostnames matching these patterns:
- `.local`, `.localhost`, `.internal`, `.corp`, `.intranet`, `.private`, `.example`, `.test`, `.invalid`, `.mail`

**Rationale:** These are common internal/private TLDs. Blocking them catches obvious internal hostnames before any DNS resolution.

### 4. Blocked URL Schemes

**Decision:** Only `http` and `https` schemes are allowed; block all others (`file`, `ftp`, `data`, etc.).

**Rationale:** The fetch tools make HTTP requests. `file://` URLs could access local files. Other schemes have no legitimate use in this context.

### 5. Configurable via Config (with Defaults)

**Decision:** Add optional config fields:
- `ssrf_blocked_ips: list[str]` — override default IP blocklist
- `ssrf_blocked_hostnames: list[str]` — override default hostname blocklist
- `ssrf_log_blocked: bool` — whether to log blocked attempts (default: True)

**Rationale:** Enterprise environments may have additional private ranges (e.g., `192.0.2.0/24` for TEST-NET-1). Config allows customization without code changes. Defaults are sensible for most users.

### 6. Error Message Strategy

**Decision:** Return human-readable error messages to the LLM. E.g., `"URL is not accessible: resolves to private network address"`.

**Rationale:** The LLM can explain to users why a reference couldn't be followed. The error is informative but generic enough not to reveal security internals.

### 7. SSRFCheckResult Dataclass

**Decision:** Create `SSRFCheckResult` with fields:
- `is_safe: bool`
- `reason: str | None` (why it was blocked, None if safe)
- `blocked_url: str` (the URL that was blocked)

**Rationale:** Structured return type makes it easy to pass results to logging, construct error messages, and test.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| User has legitimate internal GitHub instance | Config allows overriding blocklist to remove internal ranges |
| Blocking affects legitimate short-links (e.g., `http://x`) | Only well-known private TLDs blocked; single-word hosts are not blocked |
| Performance impact on URL classification | IP range checks are fast (list membership); no DNS lookups required |
| IPv6 not supported on all networks | IPv6 checks are included but can be disabled via config if needed |

## Migration Plan

1. Create `src/mattermost_summarizer/ssrf.py` with blocking logic and tests
2. Integrate into `reference_tracker.py` classify_url function
3. Add defense checks in `fetch_github_issue/impl.py` and `fetch_launchpad_bug/impl.py`
4. Add SSRF config fields to `MattermostSummarizerConfig`
5. Run existing tests to ensure no regressions
6. Deploy: No breaking changes — all defaults are safe blocklists

**Rollback:** Remove import and function calls; revert config changes if any.

## Open Questions

1. Should we block bare IPv4 addresses like `http://10.0.0.1`? **Yes**, the IP range blocking handles this.
2. Should we block IPv4-mapped IPv6 addresses (`::ffff:10.0.0.1`)? **Yes**, these should be treated as their IPv4 equivalent.
3. What about international domain names (IDN)? **Blocked TLD matching handles `.local` etc.; punycode conversion should work correctly.**
4. Should `http://0` (which resolves to 127.0.0.1) be blocked? **Yes**, the URL parser will resolve this; blocklist should catch it before network call.