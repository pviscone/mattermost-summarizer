## MODIFIED Requirements

### Requirement: Orchestrator system prompt
The orchestrator agent's system prompt SHALL be provided via AgentContext.system_message_suffix and SHALL instruct the agent to:

- Parse the permalink from the user message
- Delegate to appropriate sub-agents for the root thread
- Read the "References found" block from each delegation observation to identify URLs with their types and target sub-agents
- Decide which references to follow based on relevance (LLM-driven selection)
- Use `track_references(command="mark_followed", url="...")` before delegating for a URL
- Use `track_references(command="can_follow")` to check depth before each delegation round
- Track recursion depth and stop at max_depth
- Synthesize gathered context into a coherent summary
- Call the finish tool with structured output
- NOT call `track_references(command="classify_text", ...)` — URL classification is automatic

#### Scenario: System prompt in user message vs system message
- **WHEN** the system prompt is configured via AgentContext.system_message_suffix
- **THEN** it is sent once as the system message (benefiting from provider caching)
- **THEN** user messages contain only task-specific input (permalink URL)
- **THEN** user messages do NOT include the full system prompt each turn

#### Scenario: Orchestrator uses pre-classified URL list from observation
- **WHEN** the orchestrator receives a delegation observation with a "References found" block
- **THEN** it reads the listed URLs and their types directly from the block
- **THEN** it does NOT call `track_references(command="classify_text", ...)`
- **THEN** it decides which URLs to follow based on relevance and calls `mark_followed` for each chosen URL
