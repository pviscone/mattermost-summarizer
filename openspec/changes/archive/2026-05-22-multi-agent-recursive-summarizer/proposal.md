## Why

The current single-agent architecture has three fundamental limitations that compound as thread complexity grows:

1. **Context window pollution**: The agent fetches data via tool calls, and each tool response stays in the conversation context. A thread with 3 referenced URLs creates 3+ extra LLM calls, each re-sending all prior context.

2. **No recursive reference following**: When the agent fetches thread A which references thread B, the agent must decide to follow B, fetch it, decide to follow any references in B, and so on. This creates a linear chain of LLM calls with growing context — and the agent may miss references or over-fetch.

3. **No quality gate on output**: The agent produces a summary and outputs it directly. There's no mechanism to evaluate whether the summary captured everything important, whether the narrative is accurate, or whether action items were missed.

The OpenHands SDK provides all the primitives needed to solve these: **DelegateTool** for spawning sub-agents that run in parallel, **CriticBase** with iterative refinement for quality gates, and **AgentContext** for proper system prompt management. This change applies those primitives to create a multi-agent orchestrator architecture.

## What Changes

- Add `openhands-tools` dependency for DelegateTool
- Replace single-agent architecture with **Orchestrator + Sub-agents** via DelegateTool
- Create four specialized sub-agent types: thread_fetcher, bug_researcher, github_researcher, file_fetcher
- Implement **recursive reference following** with configurable max depth (default: 3)
- Implement **LLM-as-critic** for iterative refinement with quality scoring
- Move system prompt to `AgentContext.system_message_suffix` (proper system message, provider-side caching)
- Add summarizer config section with: max_reference_depth, critic_enabled, critic_threshold, critic_max_iterations
- Refactor summarizer.py to build orchestrator agent with critic, delegate to sub-agents, extract final summary

## Capabilities

### New Capabilities

- `orchestrator-agent`: Main orchestrator agent that parses input, delegates to sub-agents, synthesizes gathered context, and calls finish. Uses DelegateTool for spawning sub-agents and a level-specific finish tool for structured output.
- `sub-agent-registry`: Four specialized sub-agent types registered via `register_agent()`, each with its own tool set and focused system prompt: thread_fetcher (FetchThread, GetUser, FetchChannel), bug_researcher (FetchLaunchpadBug), github_researcher (FetchGitHubIssue), file_fetcher (FetchFile).
- `recursive-reference-following`: Orchestrator scans fetched content for URLs (Mattermost permalinks, Launchpad bug URLs, GitHub URLs), delegates to appropriate sub-agents, and repeats up to max_depth levels. LLM-driven decision: orchestrator decides which references to follow rather than following all of them.
- `llm-critic`: Custom CriticBase implementation that reads original thread content + fetched context + produced summary, evaluates via LLM rubric, and returns CriticResult with score and feedback. Enables iterative refinement when quality is below threshold.
- `summarization-critic-config`: Configuration for the critic: success_threshold (default 0.7), max_iterations (default 2), and level-aware rubric evaluation.

### Modified Capabilities

- `mattermost-summarizer`: REQ-005 (Agent-based Summarization) changes from single-agent-with-tools to orchestrator-agent-with-delegate-and-finish. REQ-006 (Stop Condition) extends to include critic evaluation as the quality gate, not just StuckDetector. New REQ-019 adds multi-agent architecture with orchestrator and sub-agents. New REQ-020 adds recursive reference following with configurable depth. New REQ-021 adds LLM-as-critic with iterative refinement. New REQ-022 adds system prompt via AgentContext.

## Impact

- **New dependency**: `openhands-tools` package for DelegateTool
- **New package**: `src/mattermost_summarizer/subagents/` with sub-agent factory functions
- **New module**: `src/mattermost_summarizer/critic.py` with SummarizationCritic class
- **Changes to**: `agent.py` (orchestrator building), `summarizer.py` (orchestration loop), `config.py` (new config fields), `tools/__init__.py` (tool distribution to sub-agents)
- **Config**: New `[summarizer]` TOML section with max_reference_depth, critic_enabled, critic_threshold, critic_max_iterations
- **Tool distribution**: Tools no longer all given to one agent — they are distributed to sub-agents based on specialty