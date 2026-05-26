# Architecture: mattermost-summarizer

---

## Overall Request Flow

```
summarize.py
    │
    ▼ main()
┌──────────────────────────────────────────────────────────────────┐
│  MattermostSummarizer.summarize()  [summarizer.py]              │
│                                                                  │
│  1. parse_permalink(url)  ──► post_id                           │
│  2. MattermostClient(base_url, token)                           │
│  3. load_config() ──► max_reference_depth, critic_*, level     │
│  4. Prefetch root thread via FetchThreadExecutor                │
│  5. register_subagents(client) ──► 4 agent types + delegate    │
│  6. build_orchestrator_agent(llm, level, critic, tracker)      │
│  7. LocalConversation(agent, workspace, visualizer)            │
│  8. conversation.send_message(thread_text + addendum)          │
│  9. Loop: conversation.run() up to 20 iterations                │
│  10. _extract_finish_action(conversation) ──► SummaryResult    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Architecture

The system uses a single **Orchestrator Agent** that delegates reference fetching to **specialized sub-agents** transparently via the `fetch_reference` tool.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                              │
│                                                                         │
│  System prompt: AgentContext.system_message_suffix (ORCHESTRATOR_PROMPT)│
│  Tools:                                                                 │
│    • fetch_reference  ──► FetchReferenceExecutor (spawns sub-agents)   │
│    • finish           ──► level-specific finish tool                   │
│  Critic: SummarizationCritic (iterative refinement, optional)          │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Turn 1: Read prefetched root thread text                        │ │
│  │         (injected in initial user message)                       │ │
│  │         Call fetch_reference(url=<permalink>)                    │ │
│  │         → FetchReferenceExecutor spawns thread_fetcher           │ │
│  │         → Returns thread content + "References found:" block     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                          │                                              │
│                          ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Turn 2: LLM sees references in the result block                 │ │
│  │                                                                   │ │
│  │  Found:                                                           │ │
│  │    • bugs.launchpad.net/12345                                     │ │
│  │    • github.com/canonical/mattermost/pull/789                     │ │
│  │    • chat.canonical.com/canonical/pl/xyz789                       │ │
│  │                                                                   │ │
│  │  Calls fetch_reference on each relevant URL                      │ │
│  │  → FetchReferenceExecutor spawns appropriate sub-agents          │ │
│  │  → bug_researcher, github_researcher, thread_fetcher            │ │
│  │  → each runs in parallel (tool_concurrency_limit=4)             │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                          │                                              │
│                          ▼ consolidated text results                     │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Turn 3: depth=2, thread xyz789 references another thread        │ │
│  │                                                                   │ │
│  │  Call fetch_reference(url=xyz789) — already pending at depth 2   │ │
│  │  → thread_fetcher fetches, finds no new refs or depth limit     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                          │                                              │
│                          ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Turn 4: All context gathered. Synthesize → call finish.         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                          │                                              │
│                          ▼                                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  CRITIC EVALUATION (if enabled)                                  │ │
│  │                                                                   │ │
│  │  LLM reads: [original thread] + [fetched context] + [summary]   │ │
│  │  Score: 0.55 — below threshold (0.7)                             │ │
│  │  → feedback injected as new user message                         │ │
│  │  → agent revises → calls finish again                           │ │
│  │  Score: 0.85 — above threshold ✓                                │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Orchestrator Tools

The orchestrator sees only two tools:

| Tool | Action | Purpose |
|------|--------|---------|
| `fetch_reference` | `FetchReferenceAction(url)` | Fetch a URL transparently — handles classification, depth checks, cycle prevention, and sub-agent delegation |
| `finish` | `SummarizerFinishActionBase` | Submit the final structured summary (fields vary by level) |

`fetch_reference` is the key abstraction: the orchestrator never directly calls `delegate` or knows about sub-agents.

---

## Sub-Agent Types

Sub-agents are registered via the OpenHands SDK's `register_agent()` and spawned on-demand by `FetchReferenceExecutor` via `DelegateExecutor`.

```
┌────────────────────────┐  ┌────────────────────────┐
│   thread_fetcher       │  │   bug_researcher        │
│                        │  │                        │
│   Tools:               │  │   Tools:               │
│   • FetchThread        │  │   • FetchLaunchpadBug   │
│   • GetUser            │  │                        │
│   • FetchChannel       │  │   System prompt:        │
│                        │  │   "You are a bug        │
│   System prompt:        │  │   researcher..."        │
│   "You are a thread    │  │                        │
│   researcher..."       │  │   Returns: bug title,   │
│                        │  │   status, description,  │
│   Returns: thread      │  │   comments, impact       │
│   content + URLs       │  │                        │
└────────────────────────┘  └────────────────────────┘

┌────────────────────────┐  ┌────────────────────────┐
│  github_researcher      │  │   file_fetcher          │
│                        │  │                        │
│   Tools:               │  │   Tools:               │
│   • FetchGitHubIssue   │  │   • FetchFile           │
│                        │  │                        │
│   System prompt:        │  │   System prompt:        │
│   "You are a GitHub    │  │   "You are a file       │
│   researcher..."        │  │   researcher..."        │
│                        │  │                        │
│   Returns: issue/PR    │  │   Returns: file content │
│   title, body, state,  │  │   or "not readable"    │
│   comments, reviews    │  │                        │
└────────────────────────┘  └────────────────────────┘
```

### Sub-Agent Registration

```python
# In subagents/__init__.py

def register_subagents(client: MattermostClient | None = None) -> None:
    register_delegate_tool()  # registers the SDK's delegate tool

    register_agent("thread_fetcher",   lambda llm: create_thread_fetcher(llm, client),   "Fetches threads...")
    register_agent("bug_researcher",   lambda llm: create_bug_researcher(llm, client),   "Fetches LP bugs...")
    register_agent("github_researcher",lambda llm: create_github_researcher(llm, client),"Fetches GitHub...")
    register_agent("file_fetcher",     lambda llm: create_file_fetcher(llm, client),     "Fetches files...")
```

Each sub-agent is a full `Agent` instance with its own system prompt (via `AgentContext`) and specialty tools. They use the SDK's built-in `FinishAction` to return formatted text back to the orchestrator.

---

## FetchReference Tool: The Delegation Abstraction

```python
# subagents/fetch_reference_tool.py

class FetchReferenceExecutor:
    """Single entrypoint for the orchestrator to fetch any reference URL."""

    def __call__(self, action: FetchReferenceAction, conversation=None):
        1. classify_url(action.url) → ReferenceType + agent_type
        2. Check tracker: already followed? → cycle error
        3. Check tracker: depth exceeded? → depth error
        4. Spawn sub-agent via DelegateExecutor:
              spawn  → DelegateAction(command="spawn", ids=[agent_id], agent_types=[agent_type])
              delegate → DelegateAction(command="delegate", tasks={agent_id: "Fetch and summarize: {url}"})
        5. Receive sub-agent result text
        6. Mark URL as followed in tracker
        7. Scan result text for new URLs via classify_urls_in_text()
        8. For each new followable URL:
              tracker.register_pending(url, child_depth)
        9. Append "References found in result:" block to observation
        10. Return FetchReferenceObservation(result=full_text)
```

The orchestrator LLM only sees:
- The fetched content
- A "References found:" section listing URLs with one-sentence descriptions
- Depth status (`Depth: 1/3` etc.)

This removes the need for the orchestrator to manage cycle prevention or depth tracking itself.

---

## Recursive Reference Following

```
Depth 0: User provides permalink
    │
    ▼
Depth 1: orchestrator calls fetch_reference(permalink_url)
    │      → thread_fetcher returns root thread
    │      → Finds: LP bug, GitHub PR, Mattermost permalink
    ▼
Depth 2: orchestrator calls fetch_reference on each relevant URL
    │      → bug_researcher, github_researcher, thread_fetcher (parallel)
    │      → Each result scanned for new references
    │      → New URLs registered at pending depth=2
    ▼
Depth 3: orchestrator calls fetch_reference on new thread
    │      → thread_fetcher returns, no new refs or max_depth reached
    ▼
Stop: synthesize and finish
```

### Cycle Prevention

Handled by `ReferenceTracker` (in `tools/reference_tracker.py`):

```python
@dataclass
class ReferenceTracker:
    followed_urls: dict[str, int]   # url → depth at which it was fetched
    pending_urls:  dict[str, int]   # url → depth (pre-registered before seen by LLM)
    max_depth: int = 3

    def has_been_followed(self, url) -> bool:
        return url in self.followed_urls

    def mark_followed(self, url, depth):
        # called after successful delegation

    def register_pending(self, url, depth):
        # called when a URL is discovered in sub-agent output
```

Depth is **per-URL**, not a global counter. Siblings discovered in the same thread all share the same depth level, so `max_depth=3` allows e.g. 6 sibling URLs at depth 1 each surfacing sub-references at depth 2.

### URL Classification

| URL pattern | Sub-agent | ReferenceType |
|-------------|-----------|---------------|
| `chat.{server}/{team}/pl/{post_id}` | `thread_fetcher` | `MATTERMOST_THREAD` |
| `bugs.launchpad.net/.../+bug/{id}` | `bug_researcher` | `LAUNCHPAD_BUG` |
| `github.com/{o}/{r}/issues/{id}` | `github_researcher` | `GITHUB_ISSUE` |
| `github.com/{o}/{r}/pull/{id}` | `github_researcher` | `GITHUB_PR` |
| `files.chat.{server}/...` or `/files/{id}` | `file_fetcher` | `MATTERMOST_FILE` |

---

## Summarization Levels

Three levels with different output fields and depth defaults:

| Level | Default Depth | TL;DR | Key Findings | Narrative | Action Items | Participants | Open Questions | Context Sources |
|-------|---------------|-------|--------------|-----------|--------------|--------------|----------------|-----------------|
| `brief` | 0 | 2-3 bullets | — | — | optional | — | — | — |
| `normal` | 1 | 3-5 bullets | ✓ | ✓ | ✓ | ✓ | — | — |
| `detailed` | 3 | 3-5 bullets | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

The orchestrator receives a level-specific `addendum` appended to the user message (e.g. "Level: DETAILED (comprehensive) — produce a thorough summary with all fields...").

Each level has its own `FinishAction` subclass with typed fields and a `FinishTool` subclass registered as the SDK `finish` tool:

```python
# levels/normal.py
class NormalFinishAction(SummarizerFinishActionBase):
    tldr: str
    key_findings: list[str]
    narrative: str
    action_items: list[str]
    participants: list[str]

class NormalFinishTool(SummarizerFinishToolBase):
    @classmethod
    def create(cls): ...  # registers with SDK
```

---

## LLM-as-Critic with Iterative Refinement

```
┌──────────────────────────────────────────────────────────────────┐
│  SummarizationCritic(CriticBase)                                │
│                                                                  │
│  Configurable thresholds:                                        │
│    success_threshold = 0.7                                       │
│    max_iterations = 2                                            │
│                                                                  │
│  evaluate(events) → CriticResult(score, message)                │
│    1. _extract_gathered_context(events)                         │
│    2. _extract_finish_action(events)                            │
│    3. _build_rubric(level) → brief/normal/detailed prompt       │
│    4. _call_critic_llm(context, summary, rubric)                │
│       → LLM returns JSON: {"score": 0.85, "feedback": "..."}    │
│    5. return CriticResult(score, message)                       │
│                                                                  │
│  When score < threshold: feedback injected as user message       │
│  → agent loop continues, agent revises summary                  │
│  When score ≥ threshold or max_iterations reached: accept       │
└──────────────────────────────────────────────────────────────────┘
```

The critic is attached to the orchestrator `Agent` via the `critic=` parameter. The OpenHands SDK handles the iterative refinement loop automatically.

---

## System Prompt via AgentContext

The orchestrator uses `AgentContext(system_message_suffix=ORCHESTRATOR_PROMPT)` so the system prompt is sent as a proper system message (cached by providers like Anthropic/Gemini), not embedded in the first user message.

```
BEFORE (v1 — system prompt in user message):
  Turn 1 user message: "Summarize... [full 50-line system prompt repeated]"
  Problem: no provider-side caching benefit

AFTER (v2 — system prompt via AgentContext):
  System message: "You are a Mattermost conversation summarizer..."
  Turn 1 user message: "Summarize this thread: {url}"
  Benefit: system message cached, user messages small and clean
```

---

## Thread Pre-fetching

The root thread is fetched **before** the conversation starts, not via a tool call:

```python
# summarizer.py summarize()
fetch_executor = FetchThreadExecutor(client)
fetch_obs = fetch_executor(FetchThreadAction(post_id=post_id))
thread_text = "\n".join(item.text for item in fetch_obs.to_llm_content)
message = f"Summarize this Mattermost thread...\n\n{thread_text}\n\n{level_addendum}"
conversation.send_message(message)
```

This ensures the LLM always has the full thread content in its first turn and avoids an extra round-trip.

---

## Full Sequence: URL → SummaryResult

```
summarize(url)
  │
  ├─ parse_permalink(url) → post_id
  ├─ MattermostClient(base_url, token)
  │
  ├─ Prefetch root thread:
  │    FetchThreadExecutor(client)(FetchThreadAction(post_id=post_id))
  │    → thread_text (root post + replies with resolved usernames)
  │
  ├─ register_subagents(client)
  │    register_delegate_tool()
  │    register_agent("thread_fetcher", ...)
  │    register_agent("bug_researcher", ...)
  │    register_agent("github_researcher", ...)
  │    register_agent("file_fetcher", ...)
  │
  ├─ build_orchestrator_agent(llm, level, critic, tracker)
  │    Agent(
  │      llm=LLM(...),
  │      tools=[Tool(name="fetch_reference"), Tool(name="finish")],
  │      agent_context=AgentContext(system_message_suffix=ORCHESTRATOR_PROMPT),
  │      critic=SummarizationCritic(...) if enabled,
  │      tool_concurrency_limit=4,
  │    )
  │
  ├─ LocalConversation(agent, workspace=tmpdir, visualizer)
  ├─ send_message("Summarize... post_id=abc\n\n[thread_text]\n\n[addendum]")
  │
  └─ Loop up to 20 iterations:
       conversation.run()
       │
       │  ┌─ Orchestrator Turn 1 ─────────────────────────┐
       │  │  LLM → fetch_reference(url=<permalink>)         │
       │  │  FetchReferenceExecutor:                       │
       │  │    classify_url() → thread_fetcher             │
       │  │    spawn thread_fetcher sub-agent              │
       │  │    delegate "Fetch and summarize: {url}"       │
       │  │    → sub-agent fetches thread, returns text    │
       │  │    → scan result for URLs, register pending    │
       │  │    → append "References found:" block          │
       │  │  → observation back to orchestrator            │
       │  └────────────────────────────────────────────────┘
       │
       │  ┌─ Orchestrator Turn 2 ─────────────────────────┐
       │  │  LLM scans "References found:" block          │
       │  │  Calls fetch_reference on relevant URLs        │
       │  │  → bug_researcher, github_researcher, etc.    │
       │  │  → all run in parallel (concurrency limit=4)  │
       │  │  → each returns with its own refs block        │
       │  └────────────────────────────────────────────────┘
       │
       │  ┌─ Orchestrator Turn 3+ (recursive depth) ─────┐
       │  │  Continue following references until:          │
       │  │    - no new references found                   │
       │  │    - max_reference_depth reached               │
       │  │    - all refs already followed (cycle)         │
       │  └────────────────────────────────────────────────┘
       │
       │  ┌─ Final Turn ──────────────────────────────────┐
       │  │  LLM synthesizes all gathered context           │
       │  │  Calls finish(tldr=..., narrative=..., ...)    │
       │  └────────────────────────────────────────────────┘
       │
       │  ┌─ Critic Evaluation ───────────────────────────┐
       │  │  (if enabled, handled by SDK critic loop)     │
       │  │  score < threshold → revision cycle           │
       │  │  score ≥ threshold → accept and break         │
       │  └────────────────────────────────────────────────┘
       │
       └─ _extract_finish_action(conversation)
            scan state.events reversed
            find SummarizerFinishAction
            → SummaryResult(tldr, key_findings, narrative,
                           action_items, participants, metadata)
```

---

## Tool Distribution (Agent vs Sub-agent)

```
Orchestrator Agent:
  ┌─────────────────────┐
  │   fetch_reference   │  ← transparently delegates to sub-agents
  │   finish (level)    │  ← submits structured summary
  └─────────────────────┘
           │
           │ spawns via DelegateExecutor (internal)
           ▼
  ┌────────┼──────────────────────────────┐
  │        │                              │
  ▼        ▼              ▼               ▼
┌──────┐ ┌──────┐   ┌──────────┐   ┌──────────┐
│Thread│ │ Bug  │   │ GitHub    │   │ File     │
│Fetchr│ │Rsrchr│   │ Researchr│   │ Fetcher  │
│      │ │      │   │          │   │          │
│Fetch │ │Fetch │   │FetchGH   │   │FetchFile │
│Thread│ │LPBug │   │Issue     │   │          │
│GetUsr│ │      │   │          │   │          │
│Fetch │ │      │   │          │   │          │
│Chanl │ │      │   │          │   │          │
└──────┘ └──────┘   └──────────┘   └──────────┘
```

---

## Class Hierarchy

```
mattermost_summarizer
├── __init__.py
├── agent.py
│   ├── build_orchestrator_agent()    ← orchestrator with fetch_reference + finish
│   ├── build_summarizer_agent()      ← legacy single-agent (kept for rollback)
│   └── build_summarizer_agent_with_github()  ← legacy
│
├── summarizer.py
│   └── MattermostSummarizer.summarize()  ← main orchestrator loop
│
├── client.py
│   └── MattermostClient              ← httpx-based sync API client
│
├── config.py
│   └── MattermostSummarizerConfig    ← pydantic-settings (TOML + env vars)
│       ├── max_reference_depth
│       ├── critic_enabled, critic_threshold, critic_max_iterations
│       └── max_sub_agents
│
├── critic.py
│   └── SummarizationCritic(CriticBase)
│        ├── evaluate()
│        ├── _extract_gathered_context()
│        ├── _extract_finish_action()
│        ├── _build_rubric()
│        └── _call_critic_llm()
│
├── models.py
│   ├── PostData, PostThread, Channel, UserProfile, ReactionData
│   └── Re-exports from levels/: SummaryResult, SummaryMeta, etc.
│
├── utils.py
│   ├── parse_permalink()
│   ├── setup_logging() / cleanup_external_loggers()
│
├── visualizer.py
│   └── FileConversationVisualizer    ← writes agent-trace.log
│
├── tracing_patch.py
│   └── install()                     ← OTel context propagation for sub-agents
│
├── exceptions.py                     ← PermalinkError, AgentStuckError, etc.
│
├── levels/                           ← level-specific finish actions/tools/results
│   ├── __init__.py
│   ├── base.py                       ← SummaryMeta, SummaryResultBase,
│   │                                    SummarizerFinishActionBase, SummarizerFinishToolBase
│   ├── brief.py                      ← BriefFinishAction, BriefSummaryResult
│   ├── normal.py                     ← NormalFinishAction, NormalSummaryResult
│   └── detailed.py                   ← DetailedFinishAction, DetailedSummaryResult
│
├── subagents/                        ← sub-agent factories + delegation tools
│   ├── __init__.py                   ← create_*() factories + register_subagents()
│   ├── delegate_tool.py              ← DelegateTool wrapper for SDK delegate
│   ├── fetch_reference_tool.py       ← FetchReferenceTool/Executor (orchestrator's single tool)
│   └── reference_tracking_tool.py    ← ReferenceTrackingTool (legacy/alt implementation)
│
└── tools/                            ← individual tool implementations
    ├── __init__.py                   ← build_mattermost_tools(), build_summarizer_tools()
    ├── reference_tracker.py          ← URL classification, ReferenceTracker, prompt building
    ├── fetch_thread/
    │   └── impl.py                   ← FetchThreadAction/Observation/Executor/Tool
    ├── fetch_channel/
    │   └── impl.py                   ← FetchChannelAction/Observation/Executor/Tool
    ├── get_user/
    │   └── impl.py                   ← GetUserAction/Observation/Executor/Tool
    ├── fetch_file/
    │   └── impl.py                   ← FetchFileAction/Observation/Executor/Tool
    ├── fetch_launchpad_bug/
    │   └── impl.py                   ← FetchLaunchpadBugAction/Observation/Executor/Tool
    └── fetch_github_issue/
        └── impl.py                   ← FetchGitHubIssueAction/Observation/Executor/Tool
```

---

## Configuration

```toml
[mattermost]
url = "https://chat.canonical.com"
token = "..."

[llm]
model = "openai/gpt-4o"
api_key = "..."
base_url = "..."

[github]
token = "ghp_..."

[summarizer]
default_level = "normal"
max_reference_depth = 3
critic_enabled = true
critic_threshold = 0.7
critic_max_iterations = 2
max_sub_agents = 500
```

Environment variables use `MM_` prefix with `_` as nested delimiter:

| TOML field | Env var |
|-----------|---------|
| `mattermost_url` | `MM_MATTERMOST_URL` |
| `llm_model` | `MM_LLM_MODEL` |
| `github_token` | `MM_GITHUB_TOKEN` |
| `summarizer_default_level` | `MM_SUMMARIZER_DEFAULT_LEVEL` |
| `max_reference_depth` | `MM_MAX_REFERENCE_DEPTH` |
| `critic_enabled` | `MM_CRITIC_ENABLED` |
| `critic_threshold` | `MM_CRITIC_THRESHOLD` |
| `critic_max_iterations` | `MM_CRITIC_MAX_ITERATIONS` |
| `max_sub_agents` | `MM_MAX_SUB_AGENTS` |

---

## Observability & Tracing

### MLflow Tracing

An MLflow server is available at `http://127.0.0.1:5000` for tracing LLM calls.

- **Experiment ID**: `0` — used for mattermost-summarizer runs
- Traces are configured via environment variables in `summarize.py` (OTLP exporter with `http/protobuf` protocol)
- View traces at `http://127.0.0.1:5000`

### OTel Context Propagation

`tracing_patch.py` monkey-patches `DelegateExecutor._delegate_tasks` and `LocalConversation._start_observability_span` to propagate OpenTelemetry trace context across thread boundaries. Without this, sub-agent spans would appear as siblings of the root conversation span instead of nesting under the `DelegateAction` span.

```
Parent thread (DelegateAction span active)
    │
    ├─ captures OTel Context
    ├─ patches threading.Thread to forward context
    │   ▼
    │   Child thread (sub-agent conversation)
    │       ├─ receives parent context via ContextVar
    │       └─ Laminar.start_span("conversation", context=parent_ctx)
    │           → sub-agent span is child of DelegateAction ✓
```

### Conversation Visualizer

`FileConversationVisualizer` writes formatted agent trace output to `agent-trace.log` instead of stdout.

---

## SDK Internals: Agent Loop (for reference)

### Setup (lazy, one-time)

```
LocalConversation.__init__()
  └─ stores agent, workspace, visualizer — no I/O yet

first run() or send_message() calls:
LocalConversation._ensure_agent_ready()
  ├─ _ensure_plugins_loaded()   loads MCP config, hooks, skills
  ├─ registers file-based agents
  └─ agent.init_state(state, on_event)
       └─ emits SystemPromptEvent(system_prompt, tools, dynamic_context)
            → appended to state.events as event[0]
```

### send_message() — Inject the Task

```
LocalConversation.send_message(text)
  └─ emits MessageEvent(source="user", content=text)
       → appended to state.events
```

### run() — The Main Loop

```
LocalConversation.run()

┌─────────────────────────────────────────────────────────────────┐
│  while True:                                                    │
│    ① check status                                               │
│       PAUSED/STUCK       → break                                │
│       FINISHED           → run stop-hooks, break               │
│       WAITING_FOR_CONFIRM→ reset to RUNNING                     │
│                                                                 │
│    ② stuck_detector.is_stuck()  (scans last 20 events)         │
│       → if stuck: set status = STUCK, break                     │
│                                                                 │
│    ③ agent.step(conversation, on_event, on_token)              │
│                                                                 │
│    ④ check WAITING_FOR_CONFIRMATION → break                     │
│    ⑤ check max_iteration_per_run   → error + break             │
└─────────────────────────────────────────────────────────────────┘
```

### agent.step() — One Iteration

```
Agent.step()

  ① pending actions?   unmatched ActionEvents → execute & return

  ② blocked message?   hook blocked last user msg → FINISHED & return

  ③ Build LLM message history
       prepare_llm_messages(state.events, condenser, llm)
       ┌─────────────────────────────────────────────────┐
       │  SystemPromptEvent   → system message            │
       │  MessageEvent(user)  → user message              │
       │  MessageEvent(agent) → assistant message         │
       │  ActionEvent         → assistant + tool_calls    │
       │  ObservationEvent    → tool result message       │
       │  AgentErrorEvent     → tool error message        │
       └─────────────────────────────────────────────────┘
       context too long + condenser? → emit CondensationRequest, return

  ④ LLM call
       make_llm_completion(llm, messages, tools=schemas)
       → calls LiteLLM → returns LLMResponse(message)

  ⑤ classify_response(message)
       TOOL_CALLS     → has message.tool_calls
       CONTENT        → non-blank text content
       REASONING_ONLY → thinking blocks only
       EMPTY          → nothing
```

### Tool Call Dispatch (TOOL_CALLS path)

```
_handle_tool_calls()

  for each tool_call in message.tool_calls:

    _get_action_event()
      ├─ parse JSON arguments
      ├─ normalize tool name
      ├─ validate args against tool.action_type (Pydantic)
      ├─ action = tool.action_from_arguments(args)
      └─ emit ActionEvent(action, tool_name, tool_call_id, thought)

    requires confirmation? → WAITING_FOR_CONFIRMATION, return

  _execute_actions()
    └─ ParallelToolExecutor.execute_batch()
         ThreadPoolExecutor — runs all tool calls in parallel
         ┌───────────────────────────────────────────────────┐
         │  tool.__call__(action, conversation)              │
         │    = ToolExecutor.__call__(action, conversation)  │
         │    returns Observation                            │
         │  → emit ObservationEvent  (or AgentErrorEvent)   │
         └───────────────────────────────────────────────────┘
    └─ batch.finalize()
         if finish tool called → set status = FINISHED
```

### Parallel Tool Execution

`FetchReferenceTool` declares resources per-URL to allow concurrent fetching:

```python
class FetchReferenceTool(ToolDefinition[...]):
    def declared_resources(self, action: FetchReferenceAction) -> DeclaredResources:
        # Lock on the URL to prevent duplicate fetches, but allow
        # different URLs to run concurrently.
        return DeclaredResources(keys=(f"url:{action.url}",), declared=True)
```

### Stuck Detector

```
StuckDetector.is_stuck()                  stuck_detector.py
  scans last 20 events since last user message
  checks 4 patterns:

  ┌──────────────────────────────────────────────────────────┐
  │ repeating_action_observation                             │
  │   same action + same observation  ≥ 4 times             │
  │                                                          │
  │ repeating_action_error                                   │
  │   same action + all errors        ≥ 4 times             │
  │                                                          │
  │ monologue                                                │
  │   N consecutive agent MessageEvents with no user input  │
  │                                                          │
  │ alternating_action_observation                           │
  │   A/B/A/B pattern in event pairs                        │
  └──────────────────────────────────────────────────────────┘
  equality ignores IDs — compares action, thought, tool_name,
  observation, error content
```

---

## v1 Reference: Original Single-Agent Flow (preserved for rollback context)

```
  URL: https://mattermost.example.com/team/pl/abc123
       │
       ▼ parse_permalink()
  post_id = "abc123"
       │
       ▼ build_summarizer_agent() with ALL tools:
       │    FetchThread, GetUser, FetchChannel,
       │    FetchFile, FetchLaunchpadBug, FetchGitHubIssue, finish
       │
       ▼ LLM prompt: "Summarize... post_id=abc123"
       │
       │  LLM calls fetch_thread(post_id="abc123")
       ▼
  FetchThreadExecutor
    → client.get_post_thread("abc123")
    → resolves user IDs → usernames
    → FetchThreadObservation(root_post, replies, channel_id, ...)
       │
       │  LLM (optionally) calls fetch_channel(channel_id=...)
       ▼
  FetchChannelExecutor
    → client.get_channel(channel_id)
    → FetchChannelObservation(name, purpose, ...)
       │
       │  LLM calls finish(tldr=..., key_findings=..., narrative=...,
       ▼                    action_items=..., participants=...)
  SummarizerFinishExecutor → SummarizerFinishObservation(success=True)
       │
       │  conversation ends
       ▼
  _extract_finish_action() scans conversation.state.events
    → finds SummarizerFinishAction
    → SummaryResult(tldr, key_findings, narrative, action_items, participants)
       │
       ▼
  printed to stdout as Markdown
```
