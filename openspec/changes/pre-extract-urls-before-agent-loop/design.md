## Context

The orchestrator currently instructs the LLM to call `track_references(command="classify_text", url="<full thread text>")` after receiving delegation results. This passes the entire thread content (potentially thousands of tokens) as a tool argument, causing the LLM to echo it back verbatim in its output action (~40K tokens). That 40K-token action then becomes part of the conversation history and is re-sent on every subsequent LLM call, inflating context from ~10K to 693K tokens over a session.

`ReferenceTracker.classify_urls_in_text()` is a pure Python regex function — it requires no LLM. The problem is architectural: URL classification is exposed as an LLM tool when it should happen transparently in the Python layer.

The `DelegateExecutor` lives in the SDK and constructs `DelegateObservation.from_text(text=output_text)` at the end of `_delegate_tasks`. Our own `DelegateTool` wraps the SDK tool, giving us a natural intercept point.

## Goals / Non-Goals

**Goals:**
- URL classification runs in Python immediately after a delegation completes, before the observation is delivered to the LLM
- Delegation observations include a compact, pre-classified URL list appended to the result text
- The `classify_text` command is removed from the `track_references` tool so the LLM cannot trigger it
- The orchestrator prompt is updated to read the pre-classified URL list from delegation results instead of calling `classify_text`
- Context growth per LLM turn is reduced by ~40K tokens on the first reference-following round

**Non-Goals:**
- Changing how the LLM *selects* which URLs to follow (LLM-driven relevance filtering remains)
- Changing sub-agent behavior or delegation mechanics
- Altering token usage from sub-agent turns

## Decisions

### Decision: Wrap DelegateObservation post-processing inside a custom DelegateExecutor subclass

**Chosen:** Subclass `DelegateExecutor` (from the SDK) in our own `DelegateTool` to override `_delegate_tasks`, calling `super()._delegate_tasks(action)` and then appending the URL classification summary to the returned observation's text before it is delivered to the LLM.

**Alternative A — Intercept in `summarizer.py` via event callbacks:** The `_on_finish_callback` pattern exists but only fires for finish events. Injecting a synthetic user message with URL classification after each delegation round would add an extra conversation turn and complicate the flow.

**Alternative B — Have thread_fetcher / sub-agents return pre-classified URLs themselves:** Requires modifying every sub-agent's output format, adding coupling between sub-agents and the reference tracking concern.

**Alternative C — Keep `classify_text` but truncate the input:** Would require fragile truncation logic and still burns tokens on the tool call round-trip.

**Rationale for chosen approach:** The custom executor is already the pattern used in `DelegateTool`. Subclassing `DelegateExecutor` keeps the intercept co-located with the tool, is minimally invasive to the SDK, and keeps sub-agents unaware of reference tracking.

### Decision: Append classified URLs as a structured suffix to DelegateObservation text

**Chosen:** After `super()._delegate_tasks()` returns, call `classify_urls_in_text()` on the combined result text, then append a compact block:

```
--- References found ---
1. https://github.com/canonical/cloud-init/issues/6844 (github_issue → github_researcher)
2. https://bugs.launchpad.net/ubuntu/+bug/2098515 (launchpad_bug → bug_researcher)
Depth: 0/3 — can follow more
```

This keeps the observation self-contained without adding a new message to the conversation.

**Alternative — Return structured JSON in the observation:** The SDK's `DelegateObservation.from_text` only accepts a text string; adding structured data would require deeper SDK changes.

### Decision: Remove `classify_text` from `track_references` tool description and executor

The LLM should not be able to invoke `classify_text` now that classification happens transparently. Removing it from the tool description prevents the model from using it; removing the executor branch keeps the code clean.

## Risks / Trade-offs

**[Risk] DelegateExecutor SDK changes break the subclass** → Mitigation: The subclass only calls `super()._delegate_tasks()` and processes the returned `DelegateObservation`; it doesn't override spawn logic or internal threading. If the SDK changes `_delegate_tasks`'s signature, tests will catch it immediately.

**[Risk] URL classification on very large delegation results is slow** → Mitigation: `classify_urls_in_text` is regex-only and runs in microseconds even on multi-thousand-word strings. No meaningful latency impact.

**[Risk] Orchestrator prompt update breaks existing behavior** → Mitigation: The prompt change is strictly additive (replacing "call classify_text" with "read the References found block"). Existing `mark_followed`, `is_followed`, `can_follow`, `increment_depth` commands are untouched.

**[Trade-off] The delegation observation grows slightly** → Each observation gets a small "References found" suffix (~5–20 lines). This is negligible compared to the ~40K token saving from eliminating `classify_text`.

## Migration Plan

1. Add `ReferenceTrackingDelegateExecutor` subclass in `delegate_tool.py` that calls `super()._delegate_tasks()` and appends the classified URL block.
2. Update `DelegateTool.create()` to use the new executor.
3. Remove `classify_text` branch from `ReferenceTrackingExecutor.__call__` and from the `ReferenceTrackingTool` description string.
4. Remove `classify_text` from `ReferenceTrackingAction` docs (no schema change needed — `command: str` stays).
5. Update `ORCHESTRATOR_PROMPT` in `agent.py`: replace the `classify_text` workflow example with instructions to read the "References found" block from delegation results.
6. Update / remove tests that exercise `classify_text` via the LLM tool; add tests for the Python-side URL injection in `DelegateTool`.

No config changes. No breaking changes to the public API. Rollback: revert the above files; the old `classify_text` path is restored.

## Open Questions

- Should already-followed URLs be filtered *out* of the "References found" suffix, so the LLM never even sees them? This would further reduce noise but requires the tracker to be accessible inside the executor at observation-construction time (it already is, since `ReferenceTracker` is passed to both tools). **Preferred:** yes, filter already-followed URLs out of the suffix.
