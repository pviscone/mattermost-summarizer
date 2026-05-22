## Context

The summarizer agent currently has four tools: `FetchThread`, `GetUser`, `FetchChannel`, and `finish`. Real Mattermost threads routinely reference other threads (via permalinks), file attachments, Launchpad bugs, and GitHub issues/PRs. The agent cannot follow these references today, producing summaries that miss important context.

All new tools follow the established pattern: a `ToolDefinition` subclass with a `create()` classmethod, an `Action`, an `Observation`, and a `ToolExecutor`. External tools (`FetchLaunchpadBug`, `FetchGitHubIssue`) require an HTTP client but no Mattermost client.

## Goals / Non-Goals

**Goals:**
- Add `FetchFile` tool — fetch Mattermost attachment content via the existing `MattermostClient`; return "not readable" signal for binary/unsupported files
- Add `FetchLaunchpadBug` tool — fetch public Launchpad bug data (title, description, status, comments) via Launchpad REST API
- Add `FetchGitHubIssue` tool — fetch public GitHub issue or PR data (title, description, status, metadata, review comments) via GitHub REST API; support optional `github_token` for authenticated requests
- Add `github_token` to `MattermostSummarizerConfig` as an optional field with `MM_GITHUB_TOKEN` env var support
- Register all new tools with the agent in `agent.py` and `tools/__init__.py`
- Update system prompt to guide the agent on when to follow references

**Non-Goals:**
- Private Launchpad bugs (OAuth required) — deferred
- Launchpad auth token — deferred
- GitHub PR diff content — deferred
- Binary file processing (images, PDFs via vision/OCR) — deferred to v3
- Paginated thread fetching — separate v2 concern, not in this change
- Post summary back to Mattermost — separate v2 concern, not in this change

## Decisions

### D1: Separate HTTP client for external tools, not reusing `MattermostClient`

External tools (Launchpad, GitHub) use plain `httpx.Client` instances, not `MattermostClient`. `MattermostClient` is Mattermost-specific (base URL, Bearer auth). External tools each manage their own client with appropriate auth headers.

**Alternative considered**: A generic `HttpClient` wrapper shared across all tools. Rejected — adds complexity for no benefit at this scale; each external service has distinct auth and base URL needs.

### D2: `FetchGitHubIssue` handles both Issues and PRs in one tool

GitHub's REST API surfaces PRs under `/repos/{owner}/{repo}/issues/{number}` with identical fields plus PR-specific fields. One tool accepts any GitHub issue/PR URL and returns combined metadata. The agent does not need to distinguish at tool-selection time.

**Alternative considered**: Separate `FetchGitHubIssue` and `FetchGitHubPR` tools. Rejected — doubles the tool surface for the agent to reason about, while the underlying API call is nearly identical.

### D3: `github_token` stored as `SecretStr` under the `[github]` TOML section

Parallel structure to `[mattermost]` and `[llm]` sections. Env var: `MM_GITHUB_TOKEN`. The token is optional — unauthenticated requests are permitted but rate-limited (60/hr vs 5000/hr).

```toml
[github]
token = "ghp_..."
```

### D4: Binary detection in `FetchFile` via Content-Type header

When the Mattermost API returns a file, the response's `Content-Type` header is checked. Types outside `text/*` and `application/json` are treated as binary. The observation returns a structured `is_binary: true` field plus a human-readable message so the agent can acknowledge it gracefully.

**Alternative considered**: Try to decode all responses as UTF-8 and catch `UnicodeDecodeError`. Rejected — unreliable for binary files that happen to be valid UTF-8 sequences.

### D5: Launchpad REST API v1 (no auth for public bugs)

Launchpad exposes public bug data at `https://api.launchpad.net/1.0/bugs/{id}` as JSON. Comments are fetched from the `messages_collection_link`. No auth token required for public content.

### D6: Tool directory structure mirrors existing pattern

Each new tool lives in `src/mattermost_summarizer/tools/<tool_name>/` with `impl.py` and `__init__.py`, matching the existing `fetch_thread`, `fetch_channel`, and `get_user` structure.

## Risks / Trade-offs

- **GitHub rate limits without token** → Mitigation: surface a clear error message when rate-limited (HTTP 403/429); document `github_token` config prominently.
- **Launchpad API stability** → LP REST API v1 is stable and long-lived; low risk.
- **Agent tool proliferation** → More tools = more tokens in system prompt. Mitigated by concise tool descriptions. At 7 tools total (after this change) still well within limits.
- **Large bug/issue comments** → A bug with hundreds of comments could be very large. Mitigation: cap comments returned (e.g., first 50 comments) and note truncation in the observation.
