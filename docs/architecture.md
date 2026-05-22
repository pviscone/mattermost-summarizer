# Architecture Diagrams: OpenHands SDK in mattermost-summarizer

---

## Agent Loop — Detailed Internals

### Setup (lazy, one-time)

```
LocalConversation.__init__()          local_conversation.py:96
  └─ stores agent, workspace, visualizer — no I/O yet

first run() or send_message() calls:
LocalConversation._ensure_agent_ready()   local_conversation.py:592
  ├─ _ensure_plugins_loaded()   loads MCP config, hooks, skills
  ├─ registers file-based agents
  └─ agent.init_state(state, on_event)    agent.py:350
       └─ emits SystemPromptEvent(system_prompt, tools, dynamic_context)
            → appended to state.events as event[0]
```

---

### send_message() — Inject the Task

```
LocalConversation.send_message(text)      local_conversation.py:702
  └─ emits MessageEvent(source="user", content=text)
       → appended to state.events
```

---

### run() — The Main Loop

```
LocalConversation.run()                   local_conversation.py:768

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

---

### agent.step() — One Iteration

```
Agent.step()                              agent.py:554

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

       errors:
         FunctionCallValidationError   → inject corrective MessageEvent, return
         LLMContextWindowExceedError   → CondensationRequest or raise
         LLMMalformedConversationHistoryError → CondensationRequest

  ⑤ classify_response(message)           response_dispatch.py:53
       TOOL_CALLS     → has message.tool_calls
       CONTENT        → non-blank text content
       REASONING_ONLY → thinking blocks only
       EMPTY          → nothing
```

---

### Tool Call Dispatch (TOOL_CALLS path)

```
_handle_tool_calls()                      response_dispatch.py:187

  for each tool_call in message.tool_calls:

    _get_action_event()                   agent.py:971
      ├─ parse JSON arguments
      ├─ normalize tool name
      ├─ validate args against tool.action_type (Pydantic)
      ├─ action = tool.action_from_arguments(args)
      └─ emit ActionEvent(action, tool_name, tool_call_id, thought)

    requires confirmation? → WAITING_FOR_CONFIRMATION, return

  _execute_actions()                      agent.py:491
    └─ ParallelToolExecutor.execute_batch()
         ThreadPoolExecutor — runs all tool calls in parallel
         ┌───────────────────────────────────────────────────┐
         │  tool.__call__(action, conversation)              │
         │    = ToolExecutor.__call__(action, conversation)  │
         │    returns Observation                            │
         │  → emit ObservationEvent  (or AgentErrorEvent)   │
         └───────────────────────────────────────────────────┘
    └─ batch.finalize()
         if SummarizerFinishTool called → set status = FINISHED
```

---

### Other Response Paths

```
CONTENT (text reply, no tool call)
  _handle_content_response()             response_dispatch.py:282
    emit MessageEvent(source="agent")
    status = FINISHED
    (agent answered in prose — conversation ends)

EMPTY / REASONING_ONLY
  _handle_no_content_response()          response_dispatch.py:296
    emit MessageEvent(source="agent")
    inject corrective MessageEvent(source="user", "please use a tool")
    loop continues
```

---

### Event Callback Chain (every emitted event)

```
emit(event)
  ├─ visualizer.on_event(event)
  │    FileConversationVisualizer → writes rich-formatted trace to agent-trace.log
  │
  ├─ user_callbacks(event)         (optional user-supplied)
  │
  ├─ _default_callback(event)
  │    state.events.append(event)
  │    tracks last_user_message_id
  │
  └─ hook_processor(event)
       runs session / stop / action hooks if configured
```

---

### Stuck Detector

```
StuckDetector.is_stuck()                  stuck_detector.py:62
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

### Full Sequence: URL → SummaryResult

```
summarize(url)
  │
  ├─ parse_permalink(url) → post_id
  ├─ MattermostClient(base_url, token)
  ├─ build_mattermost_tools(client)
  │    register_tool("fetch_thread",  FetchThreadTool instance)
  │    register_tool("fetch_channel", FetchChannelTool instance)
  │    register_tool("get_user",      GetUserTool instance)
  │    register_tool("finish",        SummarizerFinishTool instance)
  │
  ├─ build_summarizer_agent(model, key, tools)
  │    Agent(llm=LLM(...), tools=[Tool("fetch_thread"), ...],
  │          include_default_tools=[])
  │
  ├─ LocalConversation(agent, workspace=tmpdir, visualizer)
  ├─ send_message("Summarize... post_id=abc123...")
  │
  └─ run()
       │
       ├─ step(): LLM → fetch_thread(post_id) → thread text
       ├─ step(): LLM → fetch_channel(channel_id) → channel info
       ├─ step(): LLM → finish(tldr=..., narrative=..., ...)
       │            └─ SummarizerFinishExecutor → success=True
       │            └─ status = FINISHED
       │
       └─ _extract_finish_action(conversation)
            scan state.events reversed
            find ActionEvent.action with .tldr + .narrative
            → SummarizerFinishAction

  → SummaryResult(tldr, key_findings, narrative, action_items, participants)
  → printed to stdout as Markdown
```

---

## 1. Overall Request Flow

```
┌──────────────┐
│  summarize.py│  CLI entry point
│  main()      │
└──────┬───────┘
       │ summarize(url)
       ▼
┌──────────────────────────────────────────────────────────┐
│  MattermostSummarizer.summarize()  [summarizer.py]       │
│                                                          │
│  1. parse_permalink(url)  ──► post_id                    │
│  2. MattermostClient(base_url, token)                    │
│  3. build_mattermost_tools(client) ──► [Tool, ...]       │
│  4. build_summarizer_agent(model, key, tools) ──► Agent  │
│  5. LocalConversation(agent, workspace, visualizer)      │
│  6. conversation.send_message(prompt + post_id)          │
│  7. conversation.run()  ◄──── blocking agent loop        │
│  8. _extract_finish_action(conversation) ──► result      │
│  9. return SummaryResult                                 │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Agent Loop (inside `conversation.run()`)

```
┌─────────────────────────────────────────────────────────────────┐
│  LocalConversation.run()                                        │
│                                                                 │
│  ┌──────┐   prompt    ┌─────────────────┐                       │
│  │ User │ ──────────► │      LLM        │ (via Agent)           │
│  └──────┘             │  (e.g. GPT-4o)  │                       │
│                       └────────┬────────┘                       │
│                     tool_call  │                                 │
│                     (Action)   ▼                                 │
│                       ┌─────────────────┐                       │
│                       │  ToolExecutor   │  __call__(action)     │
│                       │  (one of 4)     │                       │
│                       └────────┬────────┘                       │
│                   Observation  │                                 │
│                   (to_llm_content) ▼                            │
│                       ┌─────────────────┐                       │
│                       │      LLM        │  next step            │
│                       └────────┬────────┘                       │
│                                │                                 │
│          repeat until SummarizerFinishAction called             │
│                                │                                 │
│                                ▼                                 │
│                         conversation ends                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Tool Architecture

```
openhands.sdk.tool.tool.ToolDefinition  (abstract)
         │
         ├── FetchThreadTool          [tools/fetch_thread/impl.py]
         │     action:   FetchThreadAction    (post_id: str)
         │     executor: FetchThreadExecutor  → client.get_post_thread()
         │     returns:  FetchThreadObservation (root_post, replies, ...)
         │
         ├── FetchChannelTool         [tools/fetch_channel/impl.py]
         │     action:   FetchChannelAction   (channel_id: str)
         │     executor: FetchChannelExecutor → client.get_channel()
         │     returns:  FetchChannelObservation (name, purpose, ...)
         │
         ├── GetUserTool              [tools/get_user/impl.py]
         │     action:   GetUserAction        (user_id: str)
         │     executor: GetUserExecutor      → client.get_user()
         │     returns:  GetUserObservation   (username, display_name, ...)
         │
         └── SummarizerFinishTool     [tools/finish/definition.py]
               action:   SummarizerFinishAction (tldr, key_findings,
               │                                 narrative, action_items,
               │                                 participants)
               executor: SummarizerFinishExecutor → returns success=True
               returns:  SummarizerFinishObservation (terminal)

Each ToolDefinition is registered globally via register_tool("name", instance)
and referenced by Agent via lightweight Tool(name="...", params={}) specs.
```

---

## 4. Tool Registration Flow

```
build_mattermost_tools(client)           [tools/__init__.py]
     │
     ├── get_fetch_thread_tool(client)   [tools/fetch_thread/__init__.py]
     │     if not _registered:
     │       instance = FetchThreadTool.create(client=client)[0]
     │       register_tool("fetch_thread", instance)   ◄── global registry
     │       _registered = True
     │     return Tool(name="fetch_thread", params={})
     │
     ├── get_fetch_channel_tool(client)  (same pattern)
     ├── get_get_user_tool(client)       (same pattern)
     └── get_finish_tool()               (same pattern, no client)

Agent(llm=llm, tools=[Tool("fetch_thread"), Tool("fetch_channel"),
                       Tool("get_user"), Tool("finish")])
```

---

## 5. Class Hierarchy

```
openhands.sdk
├── Agent                          ← created in agent.py
├── LLM                            ← wraps LiteLLM model + credentials
├── Tool (spec)                    ← Tool(name=..., params={})
├── register_tool()
├── Action                         ← base for FetchThreadAction, etc.
├── Observation                    ← base for FetchThreadObservation, etc.
├── TextContent                    ← used in to_llm_content()
│
├── tool/
│   ├── ToolExecutor               ← base for all *Executor classes
│   └── tool/
│       ├── ToolDefinition         ← base for all *Tool classes
│       └── ToolAnnotations        ← metadata (title, readOnlyHint, ...)
│
└── conversation/
    ├── LocalConversation          ← used in summarizer.py
    │   ├── send_message()
    │   ├── run()
    │   ├── state.events           ← scanned to extract SummarizerFinishAction
    │   └── stuck_detector
    └── visualizer/
        └── DefaultConversationVisualizer
              └── FileConversationVisualizer  ← writes to agent-trace.log
```

---

## 6. Data Flow: from URL to SummaryResult

```
  URL: https://mattermost.example.com/team/pl/abc123
       │
       ▼ parse_permalink()
  post_id = "abc123"
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
