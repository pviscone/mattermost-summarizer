# Spec: Recursive Reference Following

## Capability

Follow referenced URLs (Mattermost permalinks, Launchpad bugs, GitHub issues, file attachments) recursively up to a configurable depth to gather comprehensive context for summarization.

## Requirements

### Requirement: Recursive reference following
The system SHALL follow referenced URLs recursively up to a configurable depth. Depth represents the nesting level in the reference chain — siblings found in the same result share the same depth.

The `FetchReferenceExecutor`, upon completing a sub-agent delegation at depth N, SHALL pre-register each followable URL found in the result at depth N+1 on the `ReferenceTracker`. When the executor processes a new `fetch_reference` call, it SHALL look up the URL's registered depth from the tracker and check it against `max_depth`. The root URL (not found in any result) is assigned depth 0.

The `ReferenceTracker`:
- SHALL store `followed_urls: dict[str, int]` mapping each fetched URL to the depth it was fetched at
- SHALL store `pending_urls: dict[str, int]` mapping URLs surfaced in the most recent References block to their child depth
- SHALL provide `register_pending(url: str, depth: int)` for the executor to register URLs at injection time
- SHALL provide `get_depth_for(url: str) -> int | None` returning the registered depth (from pending or followed), or `None` for unregistered URLs (interpreted as depth 0 by the executor)
- SHALL provide `mark_followed(url: str, depth: int)` recording a URL as followed at the given depth
- SHALL NOT have a `current_depth: int` field or `increment_depth()` method

#### Scenario: No URLs followed (depth budget intact)
- **WHEN** the root thread result contains no followable URLs
- **THEN** no References block is appended
- **THEN** the orchestrator receives only the sub-agent result text
- **THEN** only the root thread is fetched

#### Scenario: One URL followed
- **WHEN** the root thread result references a Launchpad bug
- **THEN** the References block lists the LP bug URL at depth 1
- **THEN** the orchestrator calls `fetch_reference` for the bug URL
- **THEN** the executor registers the LP bug at depth 1 in `followed_urls`
- **THEN** after bug_researcher completes, no further URLs are surfaced (or all are at depth 2, which requires another `fetch_reference` call)
- **THEN** the orchestrator synthesizes and calls finish

#### Scenario: Three levels of nesting (chain)
- **WHEN** thread A's result surfaces thread B's URL (depth 1)
- **AND** thread B's result surfaces thread C's URL (depth 2)
- **AND** thread C's result surfaces thread D's URL (depth 3)
- **AND** `max_depth=3`
- **THEN** `fetch_reference(thread_D)` succeeds (depth 3)
- **THEN** `fetch_reference` for depth 4 URLs (surfaced from thread D) returns a depth-exceeded error
- **THEN** the orchestrator synthesizes and calls finish

#### Scenario: Multiple siblings at the same depth do not compete
- **WHEN** the root thread result surfaces 6 followable GitHub URLs at depth 1
- **THEN** all 6 calls to `fetch_reference` succeed because siblings share depth 1
- **THEN** each URL is registered at depth 1 in `followed_urls`
- **THEN** `max_depth` is not exceeded by sibling count alone

#### Scenario: Already-followed URL is not re-fetched
- **WHEN** the orchestrator calls `fetch_reference(url)` for a URL already present in `followed_urls`
- **THEN** the executor returns an error observation with "URL has already been followed"
- **THEN** no sub-agent is spawned

### Requirement: URL classification for delegation routing
Python SHALL classify URLs found in sub-agent result text and list them in a "References found in result" block appended to the result. Each URL entry SHALL include:

- The URL and its classified type (e.g. "GitHub issue/PR", "Launchpad bug")
- One sentence of surrounding context extracted from the result text (without the URL itself)

The injected block SHALL use the format:

```
---
References found in result:
Found the following references in the content:

1. <url> (<type>) — <context sentence>
2. <url> (<type>) — <context sentence>

Current depth: <N>/<max>
You may delegate to appropriate sub-agents to fetch additional context.
```

If no followable URLs are found, no block is appended and the result is returned as-is.

Classification rules (unchanged):

| URL Pattern | Type |
|---|---|
| `chat.{server}/{team}/pl/{post_id}` | Mattermost thread |
| `bugs.launchpad.net/.../+bug/{id}` | Launchpad bug |
| `github.com/{owner}/{repo}/issues/{id}` | GitHub issue/PR |
| `github.com/{owner}/{repo}/pull/{id}` | GitHub issue/PR |
| Mattermost file IDs | Mattermost file |

#### Scenario: Classification routes to correct sub-agent
- **WHEN** the result text contains a URL `https://bugs.launchpad.net/ubuntu/+bug/12345`
- **THEN** it is classified as `launchpad_bug` and listed in the References block with type "Launchpad bug"
- **THEN** the orchestrator calls `fetch_reference` for the URL

#### Scenario: Multiple URL types in same thread
- **WHEN** thread content contains a GitHub PR URL, a Launchpad bug URL, and a Mattermost permalink
- **THEN** all three are classified and listed in a single References block with context sentences
- **THEN** the orchestrator decides which are relevant and calls `fetch_reference` for each chosen URL

#### Scenario: No followable URLs found
- **WHEN** the delegation result contains no URLs matching any known pattern
- **THEN** no References block is appended
- **THEN** the raw result text is returned to the orchestrator

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
The maximum reference depth SHALL be configurable via the `[summarizer]` TOML section or environment variables.

```toml
[summarizer]
max_reference_depth = 3
```

- A value of 0 SHALL disable recursive following entirely (no external URLs, no root thread file attachments)
- A value of 1 SHALL allow following references from the root thread, but no deeper (depth 1)
- If `max_reference_depth` is explicitly set via configuration (TOML or env var), the system SHALL ALWAYS use that explicit value.
- If `max_reference_depth` is NOT explicitly set via configuration (is `None`), the system SHALL dynamically infer the effective depth based on the requested summary `level`:
  - `brief`: Depth 0
  - `normal`: Depth 1
  - `detailed`: Depth 3

#### Scenario: Custom depth explicitly configured
- **WHEN** `[summarizer] max_reference_depth = 5` is configured
- **AND** the user requests a `brief` summary
- **THEN** the explicit config wins, and the orchestrator follows references up to depth 5

#### Scenario: No explicit depth config, brief level
- **WHEN** `max_reference_depth` is not explicitly set in config
- **AND** the user requests a `brief` summary
- **THEN** the system dynamically sets the effective depth to 0
- **THEN** no external references or file attachments from the root thread are fetched

#### Scenario: No explicit depth config, normal level
- **WHEN** `max_reference_depth` is not explicitly set in config
- **AND** the user requests a `normal` summary (or uses the default level which is normal)
- **THEN** the system dynamically sets the effective depth to 1
- **THEN** references found in the root thread are fetched, but their children are not

#### Scenario: Depth limit prevents infinite recursion
- **WHEN** thread A references B, B references C, C references D, etc. (chain)
- **THEN** the orchestrator stops delegating at effective max_reference_depth
- **THEN** no infinite delegation loop occurs