## ADDED Requirements

### Requirement: Sub-agent registration
The system SHALL register four specialized sub-agent types via `register_agent()`:

- `thread_fetcher`: Fetches Mattermost threads and user/channel data
- `bug_researcher`: Fetches Launchpad bug details
- `github_researcher`: Fetches GitHub issues and PRs
- `file_fetcher`: Fetches Mattermost file attachment content

Each sub-agent SHALL be registered with a factory function that returns an Agent configured with:
- The appropriate domain tools (not DelegateTool or finish)
- A focused system prompt for its specialty
- Inherited LLM configuration from the parent orchestrator

#### Scenario: Sub-agent factory registration
- **WHEN** the application starts
- **THEN** four sub-agent types are registered via `register_agent()`
- **THEN** each registration includes a name, factory function, and description

### Requirement: thread_fetcher sub-agent
The `thread_fetcher` sub-agent SHALL have access to:
- FetchThread tool
- GetUser tool
- FetchChannel tool

The agent SHALL use a system prompt such as: "You are a thread researcher. Fetch Mattermost threads and extract key information including any URLs or references found in the thread content."

When delegated a task, the sub-agent:
- SHALL fetch the specified thread by post ID
- SHALL resolve user IDs to display names
- SHALL include channel context
- SHALL call finish with a text summary including extracted URLs/references

#### Scenario: Thread fetcher receives delegation
- **WHEN** thread_fetcher receives a delegation task: "Fetch Mattermost thread abc123"
- **THEN** it calls FetchThread with post_id abc123
- **THEN** it calls GetUser for each unique user ID in the thread
- **THEN** it calls FetchChannel for channel context
- **THEN** it scans the thread content for URLs (permalinks, Launchpad, GitHub)
- **THEN** it calls finish with formatted text summary including extracted references

### Requirement: bug_researcher sub-agent
The `bug_researcher` sub-agent SHALL have access to:
- FetchLaunchpadBug tool

The agent SHALL use a system prompt such as: "You are a bug researcher. Fetch Launchpad bug details and summarize the findings."

When delegated a task, the sub-agent:
- SHALL fetch the specified bug by URL or ID
- SHALL format the bug title, status, importance, description, and comments
- SHALL call finish with formatted text summary

#### Scenario: Bug researcher receives delegation
- **WHEN** bug_researcher receives a delegation task: "Fetch Launchpad bug 12345"
- **THEN** it calls FetchLaunchpadBug with bug_url_or_id "12345"
- **THEN** it calls finish with formatted text summary of the bug

### Requirement: github_researcher sub-agent
The `github_researcher` sub-agent SHALL have access to:
- FetchGitHubIssue tool

The agent SHALL use a system prompt such as: "You are a GitHub researcher. Fetch GitHub issue or PR details and summarize the findings."

When delegated a task, the sub-agent:
- SHALL fetch the specified issue or PR by URL
- SHALL format the title, state, body, labels, assignees, and comments
- SHALL call finish with formatted text summary

#### Scenario: GitHub researcher receives delegation
- **WHEN** github_researcher receives a delegation task: "Fetch github.com/canonical/mattermost/pull/789"
- **THEN** it calls FetchGitHubIssue with the PR URL
- **THEN** it calls finish with formatted text summary of the PR

### Requirement: file_fetcher sub-agent
The `file_fetcher` sub-agent SHALL have access to:
- FetchFile tool

The agent SHALL use a system prompt such as: "You are a file researcher. Fetch Mattermost file attachment content and report its contents."

When delegated a task, the sub-agent:
- SHALL fetch the specified file by file ID
- SHALL return text content or a "not readable" signal for binary files
- SHALL call finish with formatted text summary

#### Scenario: File fetcher receives delegation
- **WHEN** file_fetcher receives a delegation task: "Fetch file abc from thread abc123"
- **THEN** it calls FetchFile with the file ID
- **THEN** if text content: it returns the content
- **THEN** if binary: it returns "File content is not readable (binary format)"
- **THEN** it calls finish with formatted text summary