## MODIFIED Requirements

### Requirement: Configuration
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

### Requirement: Agent-based Summarization
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
