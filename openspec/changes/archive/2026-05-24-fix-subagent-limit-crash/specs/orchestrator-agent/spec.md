## MODIFIED Requirements

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
