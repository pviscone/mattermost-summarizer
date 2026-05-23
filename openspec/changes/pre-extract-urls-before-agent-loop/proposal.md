## Why

The orchestrator agent currently calls `track_references(command="classify_text", url="<full thread text>")` inside the LLM conversation loop. This causes the agent to echo ~40K tokens of raw thread content into its action output, which then accumulates in every subsequent LLM call — inflating context from ~10K to 693K tokens over a single summarization session and costing ~3.3M input tokens for one thread. URL extraction is pure regex work that requires no LLM, so it should not be happening inside the LLM conversation at all.

## What Changes

- The `summarizer.py` orchestration code will extract and classify URLs from delegation results **before** passing results back to the LLM conversation, using `ReferenceTracker` directly in Python.
- The classified URL list (not raw thread text) will be injected into the user message or appended to the delegation observation so the orchestrator receives structured, compact reference data.
- The `classify_text` command will be **removed** from the `track_references` tool (it is only needed by external callers; the remaining commands — `classify`, `mark_followed`, `is_followed`, `can_follow`, `increment_depth`, `reset` — stay).
- The `ORCHESTRATOR_PROMPT` instructions for `classify_text` will be replaced with guidance to use the pre-classified URL list provided in each delegation result.

## Capabilities

### New Capabilities

- `pre-classified-delegation-results`: Delegation observations returned to the orchestrator include a structured, pre-classified URL list alongside the raw content summary, eliminating the need for the LLM to call `classify_text` itself.

### Modified Capabilities

- `recursive-reference-following`: URL classification now happens outside the LLM conversation (Python-side), not via the `classify_text` LLM tool call. The orchestrator still decides *which* URLs to follow (LLM-driven selection remains), but the extraction and classification step is no longer an LLM action. Removes `classify_text` command from the tool exposed to the LLM.
- `orchestrator-agent`: Orchestrator system prompt updated to reflect the new flow — references arrive pre-classified in delegation results; the LLM reads the list and decides which to follow.

## Impact

- `src/mattermost_summarizer/agent.py` — remove `classify_text` section from `ORCHESTRATOR_PROMPT`
- `src/mattermost_summarizer/subagents/reference_tracking_tool.py` — remove `classify_text` command from `ReferenceTrackingTool` / `ReferenceTrackingAction` / `ReferenceTrackingExecutor`
- `src/mattermost_summarizer/summarizer.py` — add post-delegation URL extraction step that calls `ReferenceTracker.classify_text()` and injects results into the delegation observation or a follow-up user message
- `src/mattermost_summarizer/tools/reference_tracker.py` — no changes needed (logic already exists in Python)
- Tests for `classify_text` tool command will be removed; tests for the Python-side extraction path will be added
