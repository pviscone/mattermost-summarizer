## Why

The agent currently sees only the thread it is asked to summarize. Real Mattermost conversations frequently reference other threads, file attachments, Launchpad bugs, and GitHub issues — all of which carry context essential for an accurate summary. Giving the agent tools to follow these references autonomously produces richer, more complete summaries without any change to the user-facing API.

## What Changes

- Add `FetchFile` tool: fetch Mattermost file attachment content; return a "not readable" signal for binary files
- Add `FetchLaunchpadBug` tool: fetch title, description, status, and comments for a public Launchpad bug
- Add `FetchGitHubIssue` tool: fetch title, description, status, metadata, and review comments for a public GitHub issue or pull request
- Add optional `github_token` config field (TOML + `MM_GITHUB_TOKEN` env var) to raise GitHub API rate limits from 60 to 5000 req/hour
- Register all new tools with the agent so it can decide autonomously when to follow references

## Capabilities

### New Capabilities

- `fetch-file`: Fetch a Mattermost file attachment by file ID; return plain text content or a structured "not readable" signal for binary/unsupported formats
- `fetch-launchpad-bug`: Fetch a public Launchpad bug by URL or ID; return title, description, status, and comments
- `fetch-github-issue`: Fetch a public GitHub issue or pull request by URL; return title, description, status, metadata, and review comments; supports optional `github_token` for authenticated requests

### Modified Capabilities

- `mattermost-summarizer`: Add `github_token` as an optional config field; register new tools with the agent

## Impact

- `src/mattermost_summarizer/tools/`: add `fetch_file.py`, `fetch_launchpad_bug.py`, `fetch_github_issue.py`
- `src/mattermost_summarizer/config.py`: add optional `github_token` field
- `src/mattermost_summarizer/summarizer.py`: register new tools with the agent
- `pyproject.toml`: no new dependencies (httpx already present; GitHub and Launchpad APIs are plain HTTP)
- No changes to `SummaryResult`, CLI, or output format
