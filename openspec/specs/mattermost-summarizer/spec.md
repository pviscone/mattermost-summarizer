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
- Agent SHALL have access to FetchThread, GetUserProfile, FetchChannel, and finish tools
- Agent SHALL use a reasoning loop (not single-shot)
- Agent SHALL call the finish tool with structured output when satisfied

### REQ-006: Stop Condition
The system SHALL use the finish tool as the primary stop condition.
- FinishAction SHALL accept: tldr, narrative, action_items, participants
- StuckDetector SHALL be enabled as a safety net
- If stuck is detected, the system SHALL return a partial result or raise an error

### REQ-007: TL;DR Output
The system SHALL produce a bullet-point TL;DR (3-5 points) capturing key outcomes and decisions.

### REQ-008: Narrative Output
The system SHALL produce a chronological narrative appendix describing who said what and how the discussion evolved.

### REQ-009: Action Items
The system SHALL extract action items, decisions, and follow-ups mentioned in the thread.

### REQ-010: Participants
The system SHALL list all participants who contributed substantively to the thread.

### REQ-011: Metadata
The system SHALL include metadata: thread length, LLM cost, model used, duration.

### REQ-012: Configuration
The system SHALL support TOML as primary config source with env var override.
- TOML file path configurable (default: `mattermost-summarizer.toml`)
- Env var prefix: `MM_`
- Precedence: env var > TOML > defaults
- Required: mattermost_url, mattermost_token, llm_api_key
- Optional: llm_model (default: openai/gpt-4o), llm_base_url

### REQ-013: OpenAI-compatible LLM
The system SHALL support any OpenAI-compatible LLM provider via base_url configuration.
- Uses LiteLLM model naming convention (provider/model_name)
- base_url SHALL default to None (provider default)

### REQ-014: HTTP Client
The system SHALL use httpx (raw) for Mattermost API communication.
- Sync client (matching OpenHands tool execution model)
- Shared instance across tool executors for connection pooling
- Bearer token authentication

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
