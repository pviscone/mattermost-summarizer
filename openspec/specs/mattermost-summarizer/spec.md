# Spec: Mattermost Conversation Summarizer

## Capability

Summarize Mattermost conversation threads into structured output (TL;DR, narrative, action items) using an agentic AI approach.

## Requirements

### REQ-001: Permalink Input
The system SHALL accept a Mattermost permalink URL as input and extract the post ID from it.
- URL format: `https://{server}/{team}/pl/{post_id}`
- SHALL raise ValueError for invalid permalinks

### REQ-002: Thread Fetching
The system SHALL fetch the complete thread (root post + all replies) via Mattermost API v4.
- Endpoint: `GET /api/v4/posts/{post_id}/thread`
- SHALL sort replies chronologically
- SHALL auto-resolve user IDs to display names in v1

### REQ-003: User Resolution
The system SHALL resolve Mattermost user IDs to human-readable names.
- Endpoint: `GET /api/v4/users/{user_id}`
- v1: auto-resolve all users in FetchThread
- GetUserProfile tool SHALL remain available for agent-driven resolution

### REQ-004: Channel Context
The system SHALL provide channel context when available.
- Endpoint: `GET /api/v4/channels/{channel_id}`
- v1 nice-to-have: FetchChannel tool
- SHALL include channel name, purpose, and header in output

### REQ-005: Agent-based Summarization
The system SHALL use the OpenHands Software Agent SDK to perform summarization.
- Agent SHALL have access to FetchThread, GetUserProfile, FetchChannel, FetchFile, FetchLaunchpadBug, FetchGitHubIssue, and finish tools
- Agent SHALL use a reasoning loop (not single-shot)
- Agent SHALL call the finish tool with structured output when satisfied
- The system prompt SHALL instruct the agent to follow Mattermost permalinks, Launchpad bug URLs, and GitHub issue/PR URLs encountered in the thread

#### Scenario: Agent follows a Mattermost permalink in a thread
- **WHEN** the fetched thread contains a Mattermost permalink URL
- **THEN** the agent MAY call `FetchThread` with the referenced post ID to retrieve additional context

#### Scenario: Agent follows a Launchpad bug URL in a thread
- **WHEN** the fetched thread contains a `bugs.launchpad.net` URL
- **THEN** the agent MAY call `FetchLaunchpadBug` to retrieve the bug details

#### Scenario: Agent follows a GitHub issue or PR URL in a thread
- **WHEN** the fetched thread contains a `github.com/.../issues/` or `github.com/.../pull/` URL
- **THEN** the agent MAY call `FetchGitHubIssue` to retrieve the issue or PR details

### REQ-006: Stop Condition
The system SHALL use the finish tool as the primary stop condition.
- FinishAction SHALL accept: tldr, narrative, action_items, participants
- The system SHALL register an event callback on `LocalConversation` that calls `conversation.pause()` immediately upon observing the first `SummarizerFinishAction` event, stopping the run loop after exactly one finish call with no additional LLM iterations
- The summary SHALL be extracted from the conversation event log after the run exits (whether status is `FINISHED` or `PAUSED`)
- StuckDetector SHALL be enabled as a secondary safety net for cases where the finish tool is never called
- If the finish tool was never called and stuck is detected, the system SHALL raise `AgentStuckError`

### REQ-007: TL;DR Output
The system SHALL produce a bullet-point TL;DR (3-5 points) capturing key outcomes and decisions.

### REQ-008: Narrative Output
The system SHALL produce a chronological narrative appendix describing who said what and how the discussion evolved.

### REQ-009: Action Items
The system SHALL extract action items, decisions, and follow-ups mentioned in the thread.

### REQ-010: Participants
The system SHALL list all participants who contributed substantively to the thread.

### REQ-011: Metadata
The system SHALL include metadata at the bottom of the output: thread length, token stats, model used, duration.
- The `Tokens:` string SHALL be appended after `Duration` as the final metadata line.
- The system SHALL format the Tokens string exactly as: `Tokens: ↑ input {input} • cache hit {hit}% • reasoning {reasoning} • ↓ output {output} • $ {cost}`
- The `{cost}` SHALL be formatted to 2 decimal places (e.g., `0.00`).
- Token numbers `>= 1000` SHALL be divided by 1000, given two decimal places, and suffixed with `K` (e.g., `35.69K`). Token numbers `< 1000` SHALL be printed as exact integers.
- If `{hit}` evaluates to 0, the `cache hit` segment SHALL be omitted from the output.
- If `{reasoning}` evaluates to 0, the `reasoning` segment SHALL be omitted from the output.

#### Scenario: Metadata with cache hits and reasoning tokens
- **WHEN** the agent returns a summary with 35690 input tokens, 1000 cache read tokens, 653 reasoning tokens, 1820 output tokens, and 0.0042 cost
- **THEN** the metadata string includes `Tokens: ↑ input 35.69K • cache hit 2.73% • reasoning 653 • ↓ output 1.82K • $ 0.00` at the bottom.

#### Scenario: Metadata with zero reasoning and zero cache hit
- **WHEN** the agent returns a summary with 500 input tokens, 0 cache read tokens, 0 reasoning tokens, 500 output tokens, and 0.0001 cost
- **THEN** the metadata string includes `Tokens: ↑ input 500 • ↓ output 500 • $ 0.00` at the bottom.

### REQ-012: Configuration
The system SHALL support TOML as primary config source with env var override.
- TOML file path configurable (default: `mattermost-summarizer.toml`)
- Env var prefix: `MM_`
- Precedence: env var > TOML > defaults
- Required: mattermost_url, mattermost_token, llm_api_key
- Optional: llm_model (default: openai/gpt-4o), llm_base_url, github_token
- `github_token`: optional GitHub personal access token; configurable via `[github] token` in TOML or `MM_GITHUB_TOKEN` env var; used by `FetchGitHubIssue` tool to raise API rate limits from 60 to 5000 req/hour

#### Scenario: TOML config with github_token
- **WHEN** the TOML file contains a `[github]` section with `token = "ghp_..."`
- **THEN** `MattermostSummarizerConfig.github_token` is set to that value
- **THEN** the `FetchGitHubIssue` tool uses it for authenticated API requests

#### Scenario: github_token via env var
- **WHEN** the environment variable `MM_GITHUB_TOKEN` is set
- **THEN** it overrides any TOML-configured `github_token`

#### Scenario: No github_token configured
- **WHEN** neither `[github] token` in TOML nor `MM_GITHUB_TOKEN` env var is set
- **THEN** `github_token` is `None` and `FetchGitHubIssue` makes unauthenticated requests

### REQ-013: OpenAI-compatible LLM
The system SHALL support any OpenAI-compatible LLM provider via base_url configuration.
- Uses LiteLLM model naming convention (provider/model_name)
- base_url SHALL default to None (provider default)

### REQ-014: HTTP Client
The system SHALL use httpx (raw) for Mattermost API communication.
- Sync client (matching OpenHands tool execution model)
- Shared instance across tool executors for connection pooling
- Bearer token authentication

### REQ-015: Logging Separation
The system SHALL write all intermediate logs (from standard library logging, OpenHands SDK, or any internal processes) to a file, ensuring that the standard output (`stdout`) is exclusively used for the final output result of the application.

#### Scenario: Running CLI with stdout redirection
- **WHEN** the user runs the `summarize.py` CLI script and pipes the output
- **THEN** the piped `stdout` output contains only the `SummaryResult` string or JSON
- **THEN** a log file (e.g., `mattermost-summarizer.log`) is created or updated with intermediate agent and system logs

### REQ-016: TTY-aware Rich Output
The system SHALL detect whether stdout is a TTY at runtime and render `SummaryResult` with rich typography (bold section headers, colored bullets, dim metadata) when it is. When stdout is not a TTY (pipe, redirect, file), the system SHALL fall back to plain-text output identical to the current `str(result)` behaviour.

#### Scenario: Rich output on interactive terminal
- **WHEN** `summarize.py` runs and `sys.stdout.isatty()` returns `True`
- **THEN** the summary is rendered via `SummaryResult.render_rich(console)` with ANSI styling

#### Scenario: Plain fallback when piped
- **WHEN** `summarize.py` runs and stdout is piped (e.g. `summarize.py url | grep ...`)
- **THEN** the summary is rendered via `str(result)` with no ANSI escape codes

#### Scenario: Plain fallback when redirected to file
- **WHEN** `summarize.py` runs with stdout redirected (e.g. `summarize.py url > out.txt`)
- **THEN** the summary is rendered via `str(result)` with no ANSI escape codes

#### Scenario: JSON output unaffected
- **WHEN** `--output json` flag is passed
- **THEN** output is always `model_dump_json` regardless of TTY state

### REQ-017: Rich Render Method
`SummaryResult` SHALL expose a `render_rich(console: Console) -> None` method that writes the full summary to the given `Console` using typography-only rich formatting (no Panel, no Table, no Rule decorations). The method SHALL NOT alter `__str__`.

#### Scenario: Section headers are bold and colored
- **WHEN** `render_rich` is called
- **THEN** section titles (TL;DR, KEY FINDINGS, NARRATIVE, ACTION ITEMS, PARTICIPANTS) are rendered bold

#### Scenario: Bullets are visually distinct
- **WHEN** key_findings, action_items are non-empty
- **THEN** each item is prefixed with a colored bullet character

#### Scenario: Metadata line is de-emphasised
- **WHEN** `render_rich` is called
- **THEN** the metadata line (model, tokens, cost, duration) is rendered dim/muted

#### Scenario: Empty optional sections are omitted
- **WHEN** `key_findings`, `action_items`, or `participants` are empty lists
- **THEN** those sections are not rendered (same as `__str__` behaviour)

#### Scenario: Console injection for testing
- **WHEN** a `Console(file=StringIO(), force_terminal=True)` is passed to `render_rich`
- **THEN** the method writes to that console without accessing `sys.stdout` directly

### REQ-018: Rich Dependency
The project's `pyproject.toml` SHALL declare `rich` as a direct dependency with a minimum version bound, independent of any transitive dependency from `openhands-sdk`.

#### Scenario: Rich resolvable after explicit addition
- **WHEN** `uv add rich` is run
- **THEN** `uv lock` resolves without conflicts and `rich` appears in `[project.dependencies]`

## Tool Roadmap

### v1 (MVP)
- FetchThread tool (with auto user resolution)
- GetUserProfile tool
- finish tool
- FetchChannel tool (nice-to-have)

### v2
- SearchPosts tool (cross-thread references)
- FetchFile tool (attachment content)
- GetTeam tool (team context)
- Paginated thread fetching (long thread support)
- Post summary back to Mattermost

### v3
- Multi-server support
- Real-time thread monitoring
- Custom prompt templates
- Output format options (markdown, JSON, HTML)

## API Surface

```python
# High-level API
summarizer = MattermostSummarizer.from_config("config.toml")
result = summarizer.summarize("https://chat.canonical.com/canonical/pl/abc123")

# Result access
result.tldr           # str: bullet-point summary
result.narrative      # str: chronological story
result.action_items    # list[str]: decisions/todos
result.participants    # list[str]: contributor names
result.metadata        # SummaryMeta
```

## Error Classes

| Error | When |
|-------|------|
| `PermalinkError` | Invalid URL format |
| `AuthenticationError` | 401 from Mattermost |
| `ThreadNotFoundError` | 404 from Mattermost |
| `AgentStuckError` | StuckDetector triggered, no finish produced |
| `LLMError` | LLM provider errors (wrapped from OpenHands) |
| `ConfigError` | Missing required config fields |
