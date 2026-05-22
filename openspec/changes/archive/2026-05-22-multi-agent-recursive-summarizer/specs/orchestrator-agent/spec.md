## ADDED Requirements

### Requirement: Orchestrator agent architecture
The system SHALL use an orchestrator agent that coordinates sub-agents via DelegateTool to gather context and produce summaries.

The orchestrator agent:
- SHALL have access to DelegateTool and a level-specific finish tool
- SHALL NOT have access to data-fetching tools (FetchThread, FetchLaunchpadBug, etc.)
- SHALL use AgentContext with system_message_suffix for the system prompt
- SHALL delegate all data fetching to appropriate sub-agents

#### Scenario: Orchestrator delegates thread fetch
- **WHEN** the orchestrator receives a permalink to summarize
- **THEN** it delegates to a thread_fetcher sub-agent
- **THEN** it waits for the consolidated delegation result
- **THEN** it scans the returned text for references

#### Scenario: Orchestrator uses level-specific finish tool
- **WHEN** the orchestrator produces a summary
- **THEN** it calls the finish tool matching the requested summarization level (brief, normal, or detailed)

### Requirement: Orchestrator coordination loop
The orchestrator agent SHALL follow a coordination loop:

1. Parse user input (permalink URL)
2. Delegate to thread_fetcher for the root thread
3. Receive and scan results for references
4. Delegate to appropriate sub-agents for each reference found
5. Repeat steps 3-4 up to max_reference_depth levels
6. Synthesize all gathered context
7. Call finish with structured summary

#### Scenario: Orchestrator completes without recursion
- **WHEN** the root thread has no referenced URLs
- **THEN** the orchestrator skips delegation rounds 2+
- **THEN** it synthesizes only the root thread content
- **THEN** it calls finish

#### Scenario: Orchestrator completes after one recursion level
- **WHEN** the root thread references a Launchpad bug
- **THEN** the orchestrator delegates to bug_researcher after thread_fetcher
- **THEN** it synthesizes root thread + bug data
- **THEN** it calls finish

### Requirement: Orchestrator system prompt
The orchestrator agent's system prompt SHALL be provided via AgentContext.system_message_suffix and SHALL instruct the agent to:

- Parse the permalink from the user message
- Delegate to appropriate sub-agents for the root thread
- Scan fetched content for URLs (Mattermost permalinks, Launchpad bug URLs, GitHub URLs)
- Decide which references to follow based on relevance
- Delegate to appropriate sub-agents for referenced content
- Track recursion depth and stop at max_depth
- Synthesize gathered context into a coherent summary
- Call the finish tool with structured output

#### Scenario: System prompt in user message vs system message
- **WHEN** the system prompt is configured via AgentContext.system_message_suffix
- **THEN** it is sent once as the system message (benefiting from provider caching)
- **THEN** user messages contain only task-specific input (permalink URL)
- **THEN** user messages do NOT include the full system prompt each turn