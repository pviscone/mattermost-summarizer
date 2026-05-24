## Context

Currently, the orchestrator LLM starts its execution with a user message asking it to "Summarize this Mattermost thread: {permalink_url}". To fulfill this, the orchestrator's `ReferenceTracker` sees the URL and spawns a sub-agent (`thread_fetcher`), which uses `FetchThreadTool` to retrieve the thread via the Mattermost API. This adds a full LLM thought cycle and a sub-agent spawn sequence to the critical path, adding 30+ seconds of latency on slower models (like `gpt-5-mini`) before the actual summarization logic begins.

We can optimize this by retrieving the thread before initializing the LLM.

## Goals / Non-Goals

**Goals:**
- Eliminate the initial LLM thought cycle required to fetch the root Mattermost thread.
- Eliminate the overhead of spawning an initial `thread_fetcher` sub-agent for the root thread.
- Provide the LLM with the root thread text immediately.
- Prevent duplicate fetching of the root thread.

**Non-Goals:**
- Changing how *linked* threads (cross-references) are handled. They will still be fetched via the sub-agent.
- Modifying the core formatting logic of the thread itself.

## Decisions

1. **Invoke `FetchThreadExecutor` manually in Python.**
   Instead of waiting for the OpenHands agent to invoke the tool, we instantiate `FetchThreadExecutor(client)` directly inside `MattermostSummarizer.summarize()` and call it with `FetchThreadAction(post_id=post_id)`. This prevents duplicating the tool's formatting logic or introducing format drift.

2. **Inject text into the orchestrator prompt and remove the URL.**
   The resulting text from `fetch_obs.to_llm_content` is injected into the initial user message. To prevent the `ReferenceTracker` from seeing the URL and autonomously spawning a sub-agent anyway, the `{permalink_url}` is removed from the initial user prompt.

3. **Pre-seed the ReferenceTracker.**
   To ensure the agent knows the root thread has been processed and to properly manage recursion depth for sub-references, we explicitly register the permalink URL with the tracker via `tracker.mark_followed(permalink_url, depth=0)`.

4. **Derive thread length from the initial fetch observation.**
   The metadata requires a `thread_length` metric. Previously, this relied on `_estimate_thread_length(conversation)`, which scanned the event stream for tool observations. Because the root thread is now fetched outside the agent's event stream, that logic will break. We will replace it by directly computing `int(fetch_obs.total_replies) + 1` right when the fetch occurs, and removing the flawed scanning logic.

## Risks / Trade-offs

- **Risk:** Failure to fetch the thread (e.g., HTTP 404, 401).
  **Mitigation:** `FetchThreadExecutor` handles errors gracefully and returns an observation with an `error` field. We will check `fetch_obs.error` and immediately raise a `ThreadNotFoundError` or `AgentStuckError` in Python rather than continuing execution.
- **Risk:** Large context limits. Injecting the full thread upfront bloats the initial prompt.
  **Mitigation:** The thread size is identical to what would be returned in the tool observation, so the maximum context window usage remains the same (actually slightly less since the tool calling prompt overhead is gone).
