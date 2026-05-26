# Proposal: Add SSRF Protection

## Why

The system follows external URLs (GitHub, Launchpad, Mattermost threads) referenced in conversation content. A malicious actor could provide internal network URLs (e.g., `http://192.168.1.1`, `http://localhost`, `http://internal.corp`) as thread references, causing the system to attempt fetches of internal resources — a Server-Side Request Forgery (SSRF) vulnerability. This is particularly risky in multi-tenant or networked environments where internal services may be accessible.

## What Changes

- Add a new `ssrf.py` module with URL safety checking
- Integrate SSRF checks at URL classification time (reference_tracker.py)
- Add defense-in-depth checks in each external fetch tool
- Add configurable blocked IP ranges and hostnames
- Block non-HTTP(S) URL schemes (file://, data:, etc.)
- Log all blocked URL attempts for audit purposes

## Capabilities

### New Capabilities

- `ssrf-protection`: Blocks URLs that resolve to private/internal network addresses, preventing SSRF attacks during reference following. Applies to all external fetch tools (GitHub, Launchpad, Mattermost).

### Modified Capabilities

- `reference-context-enrichment`: The `extract_urls_from_text` function will now filter out URLs that fail SSRF checks before classification.
- `atomic-url-follow`: The `FetchReferenceTool` will reject URLs that fail SSRF validation before attempting to follow them.

## Impact

- **New file**: `src/mattermost_summarizer/ssrf.py`
- **Modified files**: `src/mattermost_summarizer/reference_tracker.py`, `src/mattermost_summarizer/tools/fetch_github_issue/impl.py`, `src/mattermost_summarizer/tools/fetch_launchpad_bug/impl.py`, `src/mattermost_summarizer/config.py`
- **Config changes**: New fields in `MattermostSummarizerConfig` for SSRF blocklist customization
- **Test file**: `tests/test_ssrf.py` (new)