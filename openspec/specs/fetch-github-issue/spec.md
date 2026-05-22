# Spec: Fetch GitHub Issue or Pull Request

## Capability

Fetch details of a public GitHub issue or pull request by URL.

## Requirements

### REQ-FETCH-GITHUB-ISSUE-001: Fetch public GitHub issue or pull request
The system SHALL provide a `FetchGitHubIssue` tool that fetches the details of a public GitHub issue or pull request by URL.
- The tool SHALL accept a GitHub issue or PR URL (e.g., `https://github.com/canonical/foo/issues/42` or `https://github.com/canonical/foo/pull/42`)
- The tool SHALL return: title, body, state (open/closed/merged), labels, assignees, author, created/updated dates, and comments
- For pull requests, the tool SHALL additionally return: review comments (inline + summary) and merge status
- Comments SHALL be capped at 50; the observation SHALL note how many total comments exist if truncated
- The tool SHALL use the GitHub REST API v3 (`https://api.github.com`)
- The tool SHALL support an optional `github_token` (passed at construction) to make authenticated requests; unauthenticated requests are permitted but subject to a rate limit of 60/hour
- When rate-limited (HTTP 403 or 429), the observation SHALL include a clear message advising the user to configure `github_token`

#### Scenario: Fetch a public issue by URL
- **WHEN** the agent calls `FetchGitHubIssue` with a valid GitHub issue URL
- **THEN** the observation contains the issue title, body, state, labels, assignees, author, dates, and up to 50 comments

#### Scenario: Fetch a public pull request by URL
- **WHEN** the agent calls `FetchGitHubIssue` with a valid GitHub pull request URL
- **THEN** the observation contains all issue fields plus PR-specific fields: review comments and merge status

#### Scenario: Fetch with a github_token configured
- **WHEN** `github_token` is set in config and the agent calls `FetchGitHubIssue`
- **THEN** the request is made with `Authorization: Bearer <token>` and benefits from the 5000 req/hour rate limit

#### Scenario: Rate limit exceeded without token
- **WHEN** the GitHub API returns HTTP 403 or 429 and no `github_token` is configured
- **THEN** the observation contains an error message: "GitHub API rate limit exceeded. Configure github_token in your config to increase limits."

#### Scenario: Fetch a non-existent or private repository
- **WHEN** the agent calls `FetchGitHubIssue` with a URL pointing to a private repo or non-existent issue
- **THEN** the observation contains an error message indicating the issue could not be retrieved