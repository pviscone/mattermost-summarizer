# Spec: Orchestrator Agent

## Capability

Coordinate sub-agents via DelegateTool to gather context recursively and produce summaries using an orchestrator agent architecture with level-specific finish tools.

## Requirements

### Requirement: Orchestrator agent architecture
The system SHALL use an orchestrator agent that coordinates sub-agents via DelegateTool to gather context and produce summaries.

The orchestrator agent:
- SHALL have access to DelegateTool and a level-specific finish tool
- SHALL NOT have access to data-fetching tools (FetchThread, FetchLaunchpadBug, etc.)
- SHALL use AgentContext with system_message_suffix for the system prompt
- SHALL delegate all data fetching to appropriate sub-agents
- SHALL configure the DelegateTool with a high enough limit (`max_sub_agents` default 500) to safely spawn all necessary sub-agents without artificial failures

#### Scenario: Orchestrator delegates thread fetch
- **WHEN** the orchestrator receives a permalink to summarize
- **THEN** it delegates to a thread_fetcher sub-agent
- **THEN** it waits for the consolidated delegation result
- **THEN** it scans the returned text for references

#### Scenario: Orchestrator uses level-specific finish tool
- **WHEN** the orchestrator produces a summary
- **THEN** it calls the finish tool matching the requested summarization level (brief, normal, or detailed)

#### Scenario: Orchestrator fetches multiple references
- **WHEN** a thread references multiple URLs
- **THEN** it successfully delegates to multiple fresh sub-agents (e.g. 10 GitHub PRs) without crashing on `max_children` limits

### Requirement: Orchestrator coordination loop
The orchestrator agent SHALL follow a coordination loop driven by the `FetchReferenceExecutor` and the enriched References block.

The loop:
1. The orchestrator receives a user message with the permalink URL
2. The orchestrator calls `fetch_reference(url=<permalink>)` — the `FetchReferenceExecutor` fetches the root thread via a `thread_fetcher` sub-agent
3. The observation returned includes the result text plus an optional "References found in result" block listing followable URLs with context sentences
4. The orchestrator evaluates each listed URL for relevance using the provided context sentence
5. For each relevant URL, the orchestrator calls `fetch_reference(url=<url>)`
6. Each call returns a result with (possibly) another References block
7. The orchestrator repeats steps 4-6 for any newly-surfaced references until no more References blocks appear, depth limit is reported reached, or all listed URLs judged irrelevant
8. The orchestrator synthesizes all gathered context and calls `finish`

The orchestrator SHALL NOT be responsible for tracking depth, cycles, or classification — the `FetchReferenceExecutor` handles these transparently in Python.

#### Scenario: Orchestrator completes without recursion
- **WHEN** the root thread result contains no References block
- **THEN** the orchestrator synthesizes only the root thread content and calls finish
- **THEN** no further `fetch_reference` calls are made

#### Scenario: Orchestrator completes after following relevant URLs
- **WHEN** the root thread result's References block lists a Launchpad bug URL with context "Bug tracks the root cause fix"
- **THEN** the orchestrator calls `fetch_reference` for the bug URL
- **THEN** the bug_researcher result contains no further References block
- **THEN** the orchestrator synthesizes and calls finish

#### Scenario: Orchestrator skips irrelevant references
- **WHEN** the References block lists a GitHub URL with context "Community bug report tangentially mentioned"
- **THEN** the orchestrator may judge it irrelevant and skip it
- **THEN** only references the orchestrator deems relevant are followed

#### Scenario: Orchestrator stops when depth limit reached
- **WHEN** the References block says "Maximum reference depth reached"
- **THEN** the orchestrator stops following references
- **THEN** the orchestrator synthesizes and calls finish

### Requirement: Orchestrator system prompt
The orchestrator agent's system prompt SHALL be provided via `AgentContext.system_message_suffix` and SHALL instruct the agent to:

- Parse the permalink from the user message
- Call `fetch_reference(url=<permalink>)` to fetch the root thread
- Read the result — if a "References found in result" block is present, evaluate each URL using the provided context sentence
- Call `fetch_reference(url=<url>)` for each relevant URL
- Repeat with each result until no more References blocks appear or "Maximum reference depth reached" is shown
- Synthesize gathered context into a coherent summary
- Call the finish tool with structured output

The prompt SHALL NOT instruct the agent to call `follow_url`, `classify_text`, `mark_followed`, or `track_references` — those commands no longer exist. Depth, cycle, and classification handling are automated by the `fetch_reference` tool.

#### Scenario: System prompt guides fetch_reference usage
- **WHEN** the orchestrator receives a result containing a References block
- **THEN** it calls `fetch_reference(url=<url>)` for each URL it judges relevant
- **THEN** on error responses (e.g. "Already followed", "Maximum depth reached", "Unsupported URL type"), it skips the URL and continues

#### Scenario: System prompt in user message vs system message
- **WHEN** the system prompt is configured via AgentContext.system_message_suffix
- **THEN** it is sent once as the system message (benefiting from provider caching)
- **THEN** user messages contain only task-specific input (permalink URL) and `fetch_reference` results
- **THEN** user messages do NOT include the full system prompt each turn