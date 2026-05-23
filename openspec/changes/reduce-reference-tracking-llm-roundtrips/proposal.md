## Why

The orchestrator agent spends 32% of its wall time (182s of 571s) on `track_references` tool calls — 14 LLM round-trips just to bookkeep which URLs have been seen and followed. This is pure overhead: the LLM adds no value deciding whether a URL is "already followed" or whether depth should be incremented. The fix eliminates these redundant round-trips by collapsing bookkeeping into Python and injecting pre-classified URL lists automatically after each delegation.

## What Changes

- `ReferenceTrackingTool` gains a single atomic `follow_url(url)` command that executes `is_followed` + `can_follow` + `mark_followed` + `increment_depth` in one Python call, replacing the current 4-step LLM sequence per URL
- `classify_text` command is removed from `ReferenceTrackingTool`; URL classification moves to a post-delegation Python callback
- A new post-delegation callback (injected at `LocalConversation` construction time) intercepts `DelegateObservation` events, runs `classify_urls_in_text()` on the thread content, and injects the classified URL list as a synthetic message before the LLM's next step
- `DelegateTool` is unchanged

## Capabilities

### New Capabilities

- `atomic-url-follow`: A single `follow_url` command on `track_references` that atomically checks, marks, and increments depth for a URL, replacing the 4-step sequence

### Modified Capabilities

- `recursive-reference-following`: The mechanism for tracking followed references changes — `classify_text` is removed and the 4-step per-URL protocol is replaced by `follow_url`; the orchestrator prompt is updated to match

## Impact

- `src/mattermost_summarizer/subagents/reference_tracking_tool.py`: remove `classify_text`, `is_followed`, `can_follow`, `mark_followed`, `increment_depth` commands; add `follow_url`
- `src/mattermost_summarizer/summarizer.py`: add post-delegation callback at `LocalConversation` construction; callback calls `classify_urls_in_text()` and injects result as synthetic message
- `src/mattermost_summarizer/agent.py`: update `ORCHESTRATOR_PROMPT` to reflect new `follow_url` command and removal of `classify_text`
- No new dependencies; no API or config changes
