# Proposal: Mattermost Conversation Summarizer

## Summary

A Python package that uses the OpenHands Software Agent SDK to intelligently summarize Mattermost conversation threads. Given a Mattermost permalink URL, the agent fetches the thread, resolves context (users, channels), and produces a structured summary with TL;DR and chronological narrative.

## Motivation

Mattermost threads at Canonical can be long and information-dense. Manually catching up on a 50+ reply thread is time-consuming. An agentic summarizer can:
- Follow references across threads (not just static text extraction)
- Resolve user IDs and channel context dynamically
- Produce structured, actionable output
- Learn and adapt via the OpenHands agent reasoning loop

## Architecture

```
User → MattermostSummarizer.summarize(url) → Conversation → Agent → Tools → Mattermost API
                                          ↓
                                     SummaryResult
                                     (tldr, narrative, action_items)
```

Core components:
- **Config** (pydantic + TOML): Mattermost URL/token, LLM model/key/base_url
- **MattermostClient** (httpx): Shared HTTP client for Mattermost API v4
- **Tools** (OpenHands ToolDefinition): FetchThread, GetUserProfile, FetchChannel, finish
- **Agent**: OpenHands Agent with Mattermost tools + LLM
- **Summarizer**: High-level facade that orchestrates the conversation

## Stop Condition

Agent calls a `finish` tool with the structured summary when satisfied. StuckDetector catches failure cases (repeating actions, errors, monologues).

## Tool Roadmap

| Phase | Tools | Notes |
|-------|-------|-------|
| v1 (minimum) | FetchThread, GetUserProfile, finish | Can produce "User A said X" |
| v1 (nice-to-have) | FetchChannel | Channel context for summary |
| v2 | SearchPosts, FetchFile, GetTeam | Cross-thread references, attachments |

## Package Structure

```
mattermost-summarizer/
├── pyproject.toml
├── src/
│   └── mattermost_summarizer/
│       ├── __init__.py
│       ├── config.py              ← Pydantic config (TOML + env var override)
│       ├── client.py              ← Shared httpx Mattermost API client
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── fetch_thread/
│       │   │   ├── __init__.py
│       │   │   ├── definition.py  ← Action, Observation, ToolDefinition
│       │   │   └── impl.py        ← ToolExecutor
│       │   ├── get_user/
│       │   │   ├── __init__.py
│       │   │   ├── definition.py
│       │   │   └── impl.py
│       │   ├── fetch_channel/
│       │   │   ├── __init__.py
│       │   │   ├── definition.py
│       │   │   └── impl.py
│       │   └── finish/
│       │       ├── __init__.py
│       │       ├── definition.py
│       │       └── impl.py
│       ├── agent.py               ← Agent factory (builds agent with tools + config)
│       └── summarizer.py          ← High-level API: summarize(url) → SummaryResult
```

## Config Format

TOML primary, env var override:

```toml
[mattermost]
url = "https://chat.canonical.com"
token = " MATTERMOST_TOKEN"  # or override with MM_MATTERMOST_TOKEN env var

[llm]
model = "openai/gpt-4o"
api_key = "LLM_API_KEY"       # or override with MM_LLM_API_KEY env var
base_url = "https://api.openai.com/v1"  # optional, for OpenAI-compatible providers
```

Env var prefix: `MM_` (e.g., `MM_MATTERMOST_URL`, `MM_MATTERMOST_TOKEN`, `MM_LLM_MODEL`, `MM_LLM_API_KEY`, `MM_LLM_BASE_URL`)

## Dependencies

- `openhands-sdk` — agent framework (LLM, Agent, Conversation, ToolDefinition)
- `httpx` — Mattermost API client
- `pydantic` + `pydantic-settings` — config with TOML + env var support
- `tomli` — TOML parsing (Python <3.11 compatibility)

## Non-goals

- Posting summaries back to Mattermost (could be v2)
- Real-time/streaming summarization
- Web UI
- Supporting Mattermost API v3
- Multi-server support (one config = one server)
