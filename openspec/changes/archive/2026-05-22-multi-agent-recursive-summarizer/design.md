## Context

The mattermost-summarizer uses OpenHands SDK's single-agent pattern: one agent receives all tools (FetchThread, GetUser, FetchChannel, FetchFile, FetchLaunchpadBug, FetchGitHubIssue, finish) and is given a permalink to summarize. The agent fetches the thread, decides whether to follow referenced URLs, fetches more data, and eventually calls finish with a structured summary.

Current flow for a thread with 3 referenced URLs:
```
LLM Turn 1: User message → "summarize this thread" + system prompt
LLM Turn 2: Agent calls FetchThread → response in context
LLM Turn 3: Agent calls FetchLaunchpadBug → response in context
LLM Turn 4: Agent calls FetchGitHubIssue → response in context
LLM Turn 5: Agent calls finish with summary
```

Each LLM turn re-sends all prior context. For a thread with rich references, this compounds quickly. There's also no quality gate — the summary is produced and output directly.

The OpenHands SDK (v1.23.0) provides:
- **DelegateTool**: Spawn sub-agents that run in parallel, return consolidated results
- **CriticBase**: Quality evaluation with iterative refinement loop
- **AgentContext**: Proper system prompt management (system_message_suffix)
- **register_agent()**: Register custom sub-agent types with factory functions

## Goals / Non-Goals

**Goals:**
- Enable parallel fetching via delegation (sub-agents fetch independently, don't block each other)
- Support recursive reference following (thread A → thread B → thread C) up to configurable depth
- LLM-driven reference selection (orchestrator decides what's relevant, not regex-follow-everything)
- Quality gate via LLM-as-critic with iterative refinement
- Proper system prompt via AgentContext (provider-side caching, cleaner separation)
- Clean orchestrator/sub-agent separation (orchestrator: DelegateTool + finish; sub-agents: domain tools)

**Non-Goals:**
- Changing tool implementations (FetchThread, FetchLaunchpadBug, etc. stay as-is)
- Changing output format (SummaryResult structure unchanged)
- Real-time thread monitoring (future v3)
- Multi-server support (future v3)
- Custom/user-defined summarization levels (handled by summarization-levels change)

## Decisions

### D1: DelegateTool from `openhands-tools` package

**Decision**: Add `openhands-tools` as a dependency. Import DelegateTool from `openhands.tools.delegate`.

**Rationale**: The SDK's delegation feature is in the `openhands.tools.delegate` namespace. This is a separate package from `openhands-sdk` (core SDK) but is part of the same release train. The DelegateTool provides spawn/delegate primitives that are the foundation of the architecture.

**Alternatives considered**:
- Implement delegation from scratch: rejected — DelegateTool is a well-tested SDK primitive
- Use threading/multiprocessing for parallel fetching: rejected — loses the agent's ability to decide what to fetch based on content

### D2: Sub-agents as registered factory functions via `register_agent()`

**Decision**: Each sub-agent type is registered via `register_agent(name, factory_func)` with a factory function that returns an Agent configured with the appropriate tools and a focused system prompt.

```python
def create_thread_fetcher(llm: LLM) -> Agent:
    return Agent(
        llm=llm,
        tools=[
            Tool(name="fetch_thread", params={}),
            Tool(name="get_user", params={}),
            Tool(name="fetch_channel", params={}),
        ],
        agent_context=AgentContext(
            system_message_suffix="You are a thread researcher. Fetch Mattermost threads and extract key information including any URLs or references found in the thread content.",
        ),
    )

register_agent(
    name="thread_fetcher",
    factory_func=create_thread_fetcher,
    description="Fetches Mattermost threads and extracts key information and references.",
)
```

**Rationale**: This follows the SDK's built-in pattern for custom agent types. The factory function pattern allows the orchestrator to spawn fresh sub-agents with shared LLM config but isolated tool sets. Sub-agents inherit the parent agent's LLM configuration but have their own conversation context.

**Alternatives considered**:
- Global agent instances: rejected — each delegation run should be fresh
- Class-based sub-agents: rejected — factory function pattern is simpler and matches SDK conventions

### D3: LLM-driven reference scanning (orchestrator decides)

**Decision**: After each delegation round, the orchestrator receives consolidated text results from sub-agents. The orchestrator (LLM) scans this text to identify URLs and references, then decides which ones to follow in the next delegation round. This is an LLM turn, but it replaces what would be multiple tool-call decisions in the current single-agent approach.

```python
# Orchestrator turn after receiving delegation results:
# "You fetched thread abc123. It mentions:
#   - bugs.launchpad.net/12345 (Launchpad bug, likely relevant)
#   - github.com/canonical/mattermost/pull/789 (PR, relevant)
#   - chat.canonical.com/team/pl/xyz789 (another thread, mentioned briefly)
# Which would you like to follow?"
# Agent decides: follow the bug and PR, skip the other thread
```

**Rationale**: The LLM can distinguish "this reference is central to the discussion" from "this was a passing mention". This prevents both over-fetching (following everything with regex) and under-fetching (missing important references). The cost is one extra LLM turn per depth level, which is acceptable given the parallelism gains.

**Alternatives considered**:
- Deterministic URL extraction (regex): fast, zero extra LLM cost, but follows everything — could over-fetch irrelevant references
- Fixed reference types: would require changing the scanning logic for each new reference type

### D4: Sub-agents return formatted text via built-in finish

**Decision**: Sub-agents use the SDK's built-in `FinishAction` (no custom finish tool needed). Each sub-agent calls the built-in finish with a text summary of its findings. This text becomes part of the DelegateTool's consolidated observation returned to the orchestrator.

**Rationale**: The built-in finish tool is designed for this exact purpose — signaling task completion with output. Sub-agents don't need to produce structured SummaryResult objects; they just need to return readable text that the orchestrator can incorporate into its synthesis. This is simpler than creating custom finish actions for each sub-agent type.

**Alternatives considered**:
- Custom finish actions per sub-agent: rejected — adds complexity with no benefit; the orchestrator just needs text
- Return via tool observation: rejected — the DelegateTool's consolidated observation is the intended return mechanism

### D5: LLM-as-critic with SummarizationCritic class

**Decision**: Create `SummarizationCritic(CriticBase)` that:
1. Extracts thread content + fetched context from conversation events
2. Extracts the finish action (produced summary)
3. Calls an LLM with a level-specific rubric prompt
4. Returns `CriticResult(score, message)` with quality score and specific feedback

```python
class SummarizationCritic(CriticBase):
    llm: LLM  # Separate LLM instance for evaluation
    level: SummaryLevel = SummaryLevel.NORMAL

    iterative_refinement = IterativeRefinementConfig(
        success_threshold=0.7,
        max_iterations=2,
    )

    def evaluate(self, events, git_patch=None) -> CriticResult:
        context = self._extract_gathered_context(events)
        summary = self._extract_finish_action(events)
        rubric = self._build_rubric(self.level)
        evaluation = self._call_critic_llm(context, summary, rubric)
        return CriticResult(score=evaluation.score, message=evaluation.feedback)
```

**Rationale**: An LLM-based critic can evaluate semantic quality — whether the summary captures key points, whether the narrative is accurate, whether action items are complete. Heuristic critics (checking field presence, length thresholds) only catch structural issues. The LLM critic catches quality issues that heuristics miss. The cost is ~1 LLM call per iteration, which is acceptable given the quality improvement.

**Alternatives considered**:
- Heuristic critic (field checks, length): zero extra LLM cost, but only catches structural issues
- APIBasedCritic (cloud service): requires API access, less control over rubric

### D6: Level-aware rubric for critic

**Decision**: The critic's rubric prompt varies by summarization level:
- **Brief**: Evaluate terseness, key points captured, no fluff
- **Normal**: Evaluate completeness, narrative accuracy, action items, participants
- **Detailed**: Evaluate additionally: open questions identified, sources cited, nuanced points captured

```python
def _build_rubric(self, level: SummaryLevel) -> str:
    if level == SummaryLevel.BRIEF:
        return "Evaluate whether the TL;DR captures key outcomes concisely..."
    elif level == SummaryLevel.DETAILED:
        return "Evaluate whether open questions and uncertainties are identified..."
    else:
        return "Evaluate completeness, accuracy, action items..."
```

**Rationale**: A brief summary shouldn't be penalized for lacking narrative depth. A detailed summary should be evaluated on dimensions (open questions, source citation) that don't apply to brief mode. The level is already a user-chosen parameter — the critic should respect that choice.

### D7: System prompt via AgentContext.system_message_suffix

**Decision**: The system prompt (SUMMARIZER_INSTRUCTIONS) moves from the user message (where it's re-sent every turn) to `AgentContext.system_message_suffix` (sent once as system message, cached by providers).

```python
agent_context = AgentContext(
    system_message_suffix=SYSTEM_PROMPT,
)
orchestrator = Agent(
    llm=llm,
    tools=[DelegateTool, finish_tool],
    agent_context=agent_context,
)
# User message is now just: "Summarize thread https://chat.example.com/team/pl/abc123"
```

**Rationale**: Providers like Anthropic and Gemini cache system messages. Sending the system prompt once (in the system message) rather than every turn (in the user message) reduces token usage on repeated turns. It also properly separates "who the agent is" (system) from "what it should do" (user message).

### D8: Tools distributed to sub-agents, not all to one agent

**Decision**: Tools are registered with sub-agents based on specialty:
- `thread_fetcher`: FetchThread, GetUser, FetchChannel
- `bug_researcher`: FetchLaunchpadBug
- `github_researcher`: FetchGitHubIssue
- `file_fetcher`: FetchFile

The orchestrator has only DelegateTool and finish (level-specific).

**Rationale**: Sub-agents should be focused — they fetch data, not make summarization decisions. The orchestrator coordinates, doesn't fetch. This clean separation means sub-agents can't call finish prematurely, and the orchestrator can't accidentally fetch (it must delegate).

### D9: Configurable recursion depth with default 3

**Decision**: Add `max_reference_depth` to `[summarizer]` config section (default: 3). The orchestrator tracks depth and stops delegating reference-following beyond this depth.

```toml
[summarizer]
default_level = "normal"
max_reference_depth = 3
critic_enabled = true
critic_threshold = 0.7
critic_max_iterations = 2
```

**Rationale**: Real-world recursion patterns (thread → thread → thread) typically go 2-3 levels deep before reaching stable ground. A default of 3 covers most cases without infinite recursion. The config allows users to adjust based on their use case (deeper for complex technical discussions, shallower for cost sensitivity).

## Risks / Trade-offs

- **[New dependency: openhands-tools]** → The DelegateTool is in a separate package. Verify `openhands-tools` is compatible with SDK v1.23.0 before committing. Mitigation: spike test before full implementation.

- **[Higher LLM call count per summary]** → Current architecture: 3-5 LLM calls. New architecture: 8-15+ calls (orchestrator turns + sub-agent turns + critic evaluation + potential revision). Cost is significantly higher. Mitigation: cost not a concern currently; quality improvement justifies it.

- **[Sub-agent isolation]** → Sub-agents run independently and don't share state. If thread_fetcher discovers a new URL, it can't directly delegate to github_researcher — it returns the URL to the orchestrator, which then delegates. This is intentional but adds latency (extra orchestration turn). Mitigation: the recursion pattern is explicit; depth 1 = 1 extra turn, depth 2 = 2 extra turns.

- **[Critic prompt engineering]** → The LLM-as-critic requires a well-crafted rubric prompt to evaluate quality consistently. Poor prompts lead to inconsistent scores. Mitigation: start with a simple rubric, iterate based on observed quality.

- **[Recursive delegation state]** → The orchestrator must track which references have been followed at which depth to avoid cycles and redundant fetching. Mitigation: maintain a set of followed URLs per depth level.

- **[Brief mode pipeline]** → Brief mode runs the full delegation pipeline but outputs terse summaries. This means cost is similar to normal mode despite smaller output. Mitigation: this matches user requirement ("brief should not miss context"); cost optimization can come later.

- **[Delegation visualizer complexity]** → When sub-agents are involved, the conversation visualizer log becomes more complex (multiple sub-agent conversations interleaved). Mitigation: use DelegationVisualizer from openhands-tools; monitor log readability.

## Migration Plan

**Phase 1: Dependency and skeleton**
1. Add `openhands-tools` to pyproject.toml
2. Verify DelegateTool import works
3. Create `subagents/` package with factory function stubs (returning agents with no tools, just logging)
4. Verify sub-agent registration and delegation flow works

**Phase 2: Sub-agent implementation**
1. Implement thread_fetcher factory with FetchThread, GetUser, FetchChannel tools
2. Implement bug_researcher, github_researcher, file_fetcher factories
3. Add orchestrator building in agent.py
4. Verify single-level delegation (no recursion yet)

**Phase 3: Recursive following**
1. Implement URL scanning in orchestrator after receiving delegation results
2. Implement depth tracking and stop condition
3. Verify depth 2 and depth 3 delegation work

**Phase 4: Critic integration**
1. Implement SummarizationCritic class
2. Wire critic into orchestrator agent
3. Verify iterative refinement loop works
4. Tune rubric prompts and thresholds

**Phase 5: Config and cleanup**
1. Add `[summarizer]` config section
2. Move system prompt to AgentContext
3. Update summarizer.py orchestration loop
4. Run full integration tests

**Rollback**: The single-agent architecture remains available as a fallback. If the new architecture has issues, revert to the single-agent code path (controlled by a config flag or feature flag).

## Open Questions

1. **openhands-tools package name**: Confirm the exact pip package name for DelegateTool. Is it `openhands-tools` or `openhands[tools]` or something else?

2. **Critic LLM instance**: Should the critic use the same LLM as the orchestrator (same model, different usage_id) or a separate (cheaper?) model?

3. **Delegation result format**: The consolidated observation from DelegateTool is text. Should sub-agents produce structured output (JSON) that the orchestrator parses, or is formatted text sufficient?

4. **StuckDetector coexistence**: The current architecture uses StuckDetector as a safety net. With the critic as the primary quality gate, does StuckDetector still serve a purpose?

5. **Concurrency limits**: How many concurrent sub-agents should be allowed? The DelegateTool supports `max_children` configuration. Default? Configurable?

6. **Sub-agent timeout**: Sub-agents could hang waiting for network responses. Should there be a per-sub-agent timeout that fails gracefully and returns an error observation?