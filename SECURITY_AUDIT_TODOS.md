# Security Audit Todos

## Critical Issues (P0)

### [X] 1. SSRF Vulnerability — No Restriction on Internal Network Access
**Severity:** HIGH  
**Location:** `reference_tracker.py:107-128`, `fetch_launchpad_bug/impl.py`, `fetch_github_issue/impl.py`

The `ReferenceTracker` classifies URLs and allows following Launchpad, GitHub, and Mattermost URLs, but there is **no restriction on internal network access**. An attacker could provide internal hostnames (e.g., `http://192.168.1.1`, `http://localhost`, `http://internal.corp`) and the system would attempt to fetch them.

The `sanitize_url()` function only handles IPv6 parsing issues — not internal network ranges.

**Action:** Add blocklist checking for:
- `localhost`, `127.0.0.1`, `::1`
- Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local addresses (169.254.0.0/16)
- Internal hostnames that could resolve to private IPs

---

### [ ] 2. API Tokens Stored in Config Files Without Permission Enforcement
**Severity:** HIGH  
**Location:** `config.py:97-162`, TOML config files

API tokens (`mattermost_token`, `llm_api_key`, `github_token`) are stored in TOML config files. While Pydantic v2's `SecretStr` masks values in logs, the tokens exist in plaintext on disk.

**Action:**
- Document that config files must have `0600` permissions
- Add a startup check/warning if config files are world-readable
- Emphasize in README that environment variables are preferred for production

---

## High Priority Issues (P1)

### [ ] 3. Exception Details Leaked to LLM via `str(e)` 
**Severity:** MEDIUM  
**Location:** Multiple `except Exception` blocks

Several places catch `Exception` broadly and return `error=str(e)` which may expose internal details to the LLM (file paths, network info, API structures).

Examples:
- `fetch_github_issue/impl.py:160-161`
- `fetch_launchpad_bug/impl.py:91-92`
- `fetch_reference_tool.py:92`

**Action:** Replace raw exception messages with structured, user-safe error strings that don't expose internals.

---

### [ ] 4. No Retry/Backoff for GitHub API Rate Limits
**Severity:** MEDIUM  
**Location:** `fetch_github_issue/impl.py:77-97`

The `FetchGitHubIssueExecutor` handles 403/429 responses but doesn't implement exponential backoff or request throttling.

**Action:** Add `httpx.Limits` and implement retry logic with configurable backoff for GitHub API calls.

---

## Medium Priority Issues (P2)

### [ ] 5. Thread Content Injection into LLM Context
**Severity:** MEDIUM  
**Location:** `agent.py:19-56` (SYSTEM_PROMPT)

Unsanitized Mattermost thread content is ingested into the LLM context. A malicious user could craft messages attempting to override system instructions or manipulate the `finish` tool output.

**Note:** The `tldr` field validators (`coerce_tldr_to_str` in `brief.py`, `normal.py`, `detailed.py`) are good defensive measures already in place.

**Action:**
- Add input sanitization for thread content before LLM ingestion
- Consider adding a preamble clarifying that thread content is external/user input
- Keep existing `coerce_tldr_to_str` validators as defense-in-depth

---

### [ ] 6. Global Thread Patch in `tracing_patch.py` Affects All Threads
**Severity:** MEDIUM  
**Location:** `tracing_patch.py:65-119`

`install()` monkey-patches `threading.Thread.__init__` globally, affecting **all** threading in the process, not just OpenHands threads. This could conflict with other libraries creating threads.

**Action:**
- Document that `install()` must be called early, before any other threading code
- Consider a more targeted approach (e.g., using threading local storage instead of patching `__init__`)

---

## Low Priority Issues (P3)

### [ ] 7. Log File Permissions — Conversations Written to Disk
**Severity:** LOW  
**Location:** `utils.py:13-40`

`setup_logging()` creates `mattermost-summarizer.log` with default permissions (likely 0644). Thread content, API responses, and summaries are written to this file, potentially exposing sensitive data to other users on a multi-user system.

**Action:** Create log file with `0600` permissions to restrict access to the owner.

---

### [ ] 8. Verify `max_sub_agents` Limits Total Agent Count
**Severity:** LOW  
**Location:** `fetch_reference_tool.py:43-51`

The `max_children` parameter limits delegation children, but recursive URL following could indirectly spawn agents beyond the configured limit.

**Action:** Verify that the `max_sub_agents` config truly limits total agents, not just immediate children per delegation.

---

## Informational (No Immediate Action)

### [ ] 9. Type Safety Debt in Test Code
**Severity:** INFO  
**Location:** Various test files

mypy reports ~60 errors in test files (missing type annotations, mock incompatibilities, untyped function calls).

**Note:** These don't affect production security but indicate technical debt.

---

## Security Strengths (Already Good)

The codebase has several security strengths worth preserving:

1. **Good URL Classification** — URL types are strictly limited to known patterns (GitHub, Launchpad, Mattermost)
2. **Depth Limiting Works** — `ReferenceTracker` prevents infinite recursion with per-URL depth tracking and cycle detection
3. **SecretStr Usage** — API keys use Pydantic's `SecretStr` preventing accidental logging
4. **Input Validation** — Pydantic models provide strong validation throughout
5. **Structured Error Handling** — Tools return `*Observation` objects rather than raising exceptions, keeping agent loops stable
6. **Proper Concurrency Control** — `FetchReferenceTool.declared_resources` uses `DeclaredResources` for true parallel URL fetching

---

## Completion Tracking

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 1 | SSRF — Internal network access | P0 | Open |
| 2 | Config file token permissions | P0 | Open |
| 3 | Exception detail leakage | P1 | Open |
| 4 | GitHub API rate limit backoff | P1 | Open |
| 5 | Thread content LLM injection | P2 | Open |
| 6 | Global thread patch scope | P2 | Open |
| 7 | Log file permissions | P3 | Open |
| 8 | max_sub_agents bypass | P3 | Open |
| 9 | Type safety debt | INFO | Open |
