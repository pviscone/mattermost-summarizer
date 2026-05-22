## ADDED Requirements

### Requirement: Recursive reference following
The system SHALL follow referenced URLs recursively up to a configurable depth.

The orchestrator:
- SHALL scan fetched content for URLs after each delegation round
- SHALL classify each URL by type: Mattermost permalink, Launchpad bug URL, GitHub URL, file attachment
- SHALL delegate to the appropriate sub-agent for each URL type
- SHALL track the current recursion depth
- SHALL stop delegating when depth reaches max_reference_depth

#### Scenario: Recursion depth 1 (no recursion)
- **WHEN** the root thread contains no referenced URLs
- **THEN** only thread_fetcher is delegated
- **THEN** no further delegation rounds occur
- **THEN** max_reference_depth is not exceeded

#### Scenario: Recursion depth 2
- **WHEN** the root thread references a Launchpad bug
- **THEN** after thread_fetcher, bug_researcher is delegated
- **THEN** the orchestrator checks: depth=2, continue if depth < max_depth
- **THEN** no further delegation occurs (only one reference found)

#### Scenario: Recursion depth 3
- **WHEN** thread A references thread B, and thread B references thread C
- **THEN** depth 1: thread_fetcher gets thread A
- **THEN** depth 2: thread_fetcher gets thread B
- **THEN** depth 3: thread_fetcher gets thread C
- **THEN** depth 4 would exceed max_depth=3, so thread C is not followed

### Requirement: URL classification for delegation routing
The orchestrator SHALL classify found URLs to route to the correct sub-agent:

| URL Pattern | Sub-agent |
|-------------|----------|
| `chat.{server}/{team}/pl/{post_id}` | thread_fetcher |
| `bugs.launchpad.net/.../+bug/{id}` | bug_researcher |
| `github.com/{owner}/{repo}/issues/{id}` | github_researcher |
| `github.com/{owner}/{repo}/pull/{id}` | github_researcher |
| Mattermost file IDs | file_fetcher |

#### Scenario: Classification routes to correct sub-agent
- **WHEN** the orchestrator finds a URL: "https://bugs.launchpad.net/ubuntu/+bug/12345"
- **THEN** it classifies as Launchpad bug URL
- **THEN** it delegates to bug_researcher sub-agent

#### Scenario: Multiple URL types in same thread
- **WHEN** thread content contains a GitHub PR URL, a Launchpad bug URL, and a Mattermost permalink
- **THEN** the orchestrator delegates to github_researcher, bug_researcher, and thread_fetcher respectively
- **THEN** all three delegations run in parallel (same depth level)

### Requirement: LLM-driven reference selection
The orchestrator SHALL decide which references to follow based on their relevance to the discussion, not following all references indiscriminately.

The orchestrator (LLM):
- SHALL evaluate each URL found in the fetched content
- SHALL determine whether the reference is central to the discussion or a passing mention
- SHALL skip following references that are irrelevant
- SHALL track which URLs have already been followed to avoid cycles

#### Scenario: Orchestrator skips irrelevant reference
- **WHEN** thread content mentions "see github.com/o/r/456 for details" but the issue is not discussed further
- **THEN** the orchestrator MAY decide to skip fetching that URL
- **THEN** only relevant references are delegated

#### Scenario: Orchestrator avoids duplicate fetching
- **WHEN** a URL appears in multiple threads at different depths
- **THEN** the orchestrator SHALL NOT re-fetch the same URL
- **THEN** it SHALL track followed URLs in a set per summary operation

### Requirement: Configurable recursion depth
The maximum reference depth SHALL be configurable via the `[summarizer]` TOML section.

```toml
[summarizer]
max_reference_depth = 3
```

- The default value SHALL be 3
- A value of 0 SHALL disable recursive following entirely
- A value of 1 SHALL allow only the root thread (no references followed)

#### Scenario: Custom depth of 5
- **WHEN** `[summarizer] max_reference_depth = 5` is configured
- **THEN** the orchestrator follows references up to depth 5
- **THEN** deeper references are not followed

#### Scenario: Depth limit prevents infinite recursion
- **WHEN** thread A references B, B references C, C references D, etc. (chain)
- **THEN** the orchestrator stops delegating at max_reference_depth
- **THEN** no infinite delegation loop occurs