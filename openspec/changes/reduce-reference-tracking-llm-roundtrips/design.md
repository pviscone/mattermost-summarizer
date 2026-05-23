## Context

The orchestrator agent uses a `track_references` tool to manage URL bookkeeping during recursive reference following. The current protocol requires 4 separate LLM round-trips per URL (`is_followed` → `can_follow` → `mark_followed` → `increment_depth`) plus 2 additional calls to `classify_text` per run. With 3 URLs followed across a typical run this adds up to 14 LLM round-trips that contribute ~182s of wall time (32% of total) despite the underlying Python logic running in under 10ms.

Two orthogonal problems exist:
1. **Bookkeeping overhead**: 4 LLM steps per URL for operations that are pure Python state mutation with no LLM judgment required.
2. **Classification overhead**: `classify_text` is called by the LLM to extract URLs from the 44K-char thread content — again no LLM judgment needed, pure regex + rule-based classification.

The `DelegateTool` is a generic thin wrapper and must not acquire domain-specific logic.

## Goals / Non-Goals

**Goals:**
- Eliminate the 4-step per-URL bookkeeping sequence; replace with a single atomic `follow_url` command
- Remove `classify_text` from the LLM-callable tool surface
- Automatically inject a classified URL list into the conversation after each delegation, so the LLM can make relevance decisions without calling `classify_text` itself
- Keep `DelegateTool` unchanged

**Non-Goals:**
- Removing the LLM's ability to decide *which* URLs to follow (relevance is genuine LLM work)
- Changing the `ReferenceTracker` Python class itself
- Altering sub-agent registration or the `DelegateTool` interface

## Decisions

### Decision 1: Atomic `follow_url` command replaces 4-step sequence

**Choice**: Add a `follow_url(url)` command to `ReferenceTrackingExecutor` that atomically runs `has_been_followed` check, `can_follow_deeper` check, `mark_followed`, and `increment_depth` under `tracker.lock()`, returning a single observation: success, already-followed, or depth-exceeded.

**Rationale**: The 4-step sequence exists because the LLM was designed to call each step individually, but there is no LLM judgment between steps — it always runs all 4 unconditionally. Collapsing them saves 3 round-trips per URL.

**Alternatives considered**:
- Keep 4 steps, cache at SDK layer — SDK has no per-tool result cache; would require patching SDK internals.
- Move all tracking logic to pre/post hooks — hooks are out-of-process shell commands, making shared in-memory state impossible without IPC.

The `classify`, `is_followed`, `can_follow`, `mark_followed`, `increment_depth` commands are removed (no longer advertised in the tool description). `classify_text` is also removed from the tool. `reset` is retained for test/cleanup use.

### Decision 2: Post-delegation callback injects classified URL list as synthetic message

**Choice**: In `summarizer.py`, alongside the existing `_on_finish_callback`, register a `_post_delegation_callback` closure that:
1. Checks each `event` for an observation whose `tool_name == "delegate"` (or equivalent attribute on `DelegateObservation`)
2. When detected, calls `classify_urls_in_text(obs_text, tracker)` in Python
3. Appends a synthetic user message to the conversation via `conversation.send_message(...)` with the formatted classified URL list

**Rationale**: This intercept point is fully outside `DelegateTool`, lives in orchestrator-specific code, and uses the same callback mechanism already present for `_on_finish_callback`. The `ReferenceTracker` instance is captured in the closure, so no IPC is needed.

**Alternatives considered**:
- `PostToolUse` hook (shell command): would require externalising `ReferenceTracker` state via temp file — awkward and slow.
- Modifying `DelegateTool` to call `classify_urls_in_text` — violates the generic-delegator constraint.
- `user_message_suffix` on `AgentContext` — static field, cannot update dynamically per delegation turn.

The callback determines the `obs_text` by inspecting the observation for a content/result attribute on the `DelegateObservation`. The exact attribute name is confirmed from `delegate_tool.py` during implementation.

### Decision 3: Orchestrator prompt updated to reflect new interface

The `ORCHESTRATOR_PROMPT` in `agent.py` currently instructs the LLM to call `classify_text` and the 4-step sequence. It is updated to:
- Remove `classify_text` instructions
- Remove multi-step protocol; replace with single `follow_url(url)` call
- Note that classified URLs will be provided automatically after each delegation

## Risks / Trade-offs

**[Risk] Callback fires on every event, not just delegation events** → Mitigation: guard with `isinstance(obs, DelegateObservation)` or attribute check; cost of a no-op check is negligible.

**[Risk] `send_message` during a conversation run may interleave unexpectedly** → Mitigation: the existing `_on_finish_callback` already calls `conversation.pause()` mid-run, so the SDK supports mid-run message injection. Confirm `send_message` is safe in callbacks during `run()` before implementation.

**[Risk] Removing individual commands (`is_followed`, `can_follow`, etc.) breaks any existing tests that call them directly** → Mitigation: update affected tests as part of the same PR.

**[Risk] Classified URL injection after delegation adds a synthetic message to context, slightly increasing token count per turn** → Trade-off accepted: one extra ~200-token message per delegation is far cheaper than 141s of `classify_text` LLM round-trips.

## Migration Plan

1. Update `ReferenceTrackingExecutor` and `ReferenceTrackingTool`: add `follow_url`, remove deprecated commands
2. Update `summarizer.py`: add `_post_delegation_callback` closure; pass updated `callbacks` list to `LocalConversation`
3. Update `ORCHESTRATOR_PROMPT` in `agent.py`
4. Update tests: replace old command sequences with `follow_url`; add test for callback injection
5. No config changes; no new dependencies; no migration needed for existing deployments
