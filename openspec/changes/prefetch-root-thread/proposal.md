## Why

When the summarizer agent is instantiated, especially with slower LLM models, it can take 30+ seconds and waste tokens just deciding to call `fetch_thread` for the root Mattermost thread. Since the root thread is always required to summarize the conversation, we should prefetch it before the LLM is invoked and inject its contents directly into the initial prompt.

## What Changes

- Prefetch the root Mattermost thread using `FetchThreadExecutor` directly inside `MattermostSummarizer.summarize()` before initializing the agent.
- Inject the fetched thread's formatted text directly into the orchestrator agent's initial prompt.
- Strip the Mattermost URL from the initial prompt so the LLM doesn't attempt to re-fetch it.
- Explicitly mark the root URL as visited in the `ReferenceTracker` to avoid redundant sub-agent spawns.
- Compute the root thread length from the pre-fetched observation, replacing the buggy `_estimate_thread_length` event-scanning logic.

## Capabilities

### New Capabilities

- `root-thread-prefetch`: Automatically fetching and injecting the root thread into the agent's context to optimize latency and token usage.

### Modified Capabilities

None.

## Impact

- **Performance:** Reduces initial summarization latency by bypassing a full LLM turn and tool execution round-trip (~30 seconds saved on slower models).
- **Token Usage:** Saves input and output tokens associated with the LLM reasoning about fetching the thread.
- **Codebase:** Modifies `MattermostSummarizer.summarize()` in `src/mattermost_summarizer/summarizer.py`. Removes the `_estimate_thread_length` function.
