## MODIFIED Requirements

### Requirement: Agent-based Summarization
The system SHALL use the OpenHands Software Agent SDK to perform summarization.

The architecture is **orchestrator + sub-agents**:
- The **orchestrator agent** SHALL have access to DelegateTool and a level-specific finish tool
- The orchestrator SHALL delegate all data fetching to **sub-agents**
- Sub-agents SHALL have access to domain tools based on their specialty:
  - `thread_fetcher`: FetchThread, GetUser, FetchChannel
  - `bug_researcher`: FetchLaunchpadBug
  - `github_researcher`: FetchGitHubIssue
  - `file_fetcher`: FetchFile
- Each sub-agent SHALL be registered via `register_agent()` with a factory function
- The orchestrator SHALL coordinate the delegation loop and synthesize results

The orchestrator's system prompt SHALL be provided via `AgentContext.system_message_suffix`.

#### Scenario: Orchestrator delegates thread fetch
- **WHEN** the user requests a summary
- **THEN** the orchestrator delegates to thread_fetcher
- **THEN** thread_fetcher fetches the thread and returns formatted text
- **THEN** the orchestrator scans for references and delegates further as needed
- **THEN** the orchestrator synthesizes and calls finish

### Requirement: Stop Condition
The system SHALL use the finish tool and critic evaluation as stop conditions.

Primary stop: The finish tool call signals the agent believes summarization is complete.
- The system SHALL extract the `SummarizerFinishAction` from conversation events
- The system SHALL pause the conversation upon observing the first finish action

Quality gate: The critic evaluates the summary after finish.
- If the critic score is below `success_threshold`, the orchestrator revises and calls finish again
- This loop repeats up to `max_iterations` times
- If `critic_enabled=false`, only the finish tool stop condition applies

StuckDetector remains as a tertiary safety net.

#### Scenario: Summary passes critic on first try
- **WHEN** the orchestrator calls finish with a summary
- **THEN** the critic evaluates and scores 0.85
- **THEN** the score is above threshold (0.7)
- **THEN** summarization completes without revision

#### Scenario: Summary fails critic, revision occurs
- **WHEN** the orchestrator calls finish with a summary
- **THEN** the critic evaluates and scores 0.55
- **THEN** the orchestrator receives feedback and revises
- **THEN** the orchestrator calls finish again with an improved summary

#### Scenario: Critic disabled, only finish stop applies
- **WHEN** `[summarizer] critic_enabled = false`
- **THEN** no critic evaluation occurs
- **THEN** the first finish call ends summarization

## ADDED Requirements

### Requirement: Multi-agent architecture
The system SHALL implement a multi-agent architecture with one orchestrator and multiple sub-agents.

Orchestrator responsibilities:
- Parse user input (permalink URL)
- Coordinate the delegation loop
- Scan fetched content for URLs
- Decide which references to follow
- Track recursion depth
- Synthesize gathered context
- Call finish with structured summary

Sub-agent responsibilities:
- Fetch data for their domain (thread, bug, issue, file)
- Return formatted text results to the orchestrator
- Do not call other sub-agents

#### Scenario: Architecture with four sub-agents
- **WHEN** the application starts
- **THEN** four sub-agent types are registered: thread_fetcher, bug_researcher, github_researcher, file_fetcher
- **THEN** the orchestrator has DelegateTool and finish
- **THEN** sub-agents have domain tools only

### Requirement: System prompt via AgentContext
The system prompt SHALL be provided via `AgentContext.system_message_suffix`.

- The system prompt SHALL be sent once as the system message (not in every user message)
- Providers that support system message caching (Anthropic, Gemini) SHALL benefit from this
- The user message SHALL contain only task-specific input: the permalink URL and post ID

#### Scenario: System prompt in system message, not user message
- **WHEN** the orchestrator is configured with `AgentContext(system_message_suffix=SYSTEM_PROMPT)`
- **THEN** the system prompt is sent once per conversation
- **THEN** subsequent turns do NOT re-send the full system prompt in the user message
- **THEN** user messages are small (just the task input)