## 1. Remove classify_text from ReferenceTrackingTool

- [ ] 1.1 Remove the `classify_text` branch from `ReferenceTrackingExecutor.__call__` in `subagents/reference_tracking_tool.py`
- [ ] 1.2 Remove `classify_text` from the `description` string in `ReferenceTrackingTool.create()`
- [ ] 1.3 Remove or update tests that exercise `classify_text` via the `ReferenceTrackingExecutor` directly

## 2. Add URL injection to DelegateTool

- [ ] 2.1 Subclass `DelegateExecutor` (from `openhands.tools.delegate.impl`) in `subagents/delegate_tool.py` as `ReferenceInjectingDelegateExecutor`; accept a `ReferenceTracker` instance in `__init__`
- [ ] 2.2 Override `_delegate_tasks`: call `super()._delegate_tasks(action)`, then call `classify_urls_in_text(result_text, tracker)` on the returned observation's text, append the "References found" block (including already-filtered URLs and depth status) to the observation text, and return the modified observation
- [ ] 2.3 Update `DelegateTool.create()` to accept an optional `tracker: ReferenceTracker | None` parameter and instantiate `ReferenceInjectingDelegateExecutor(tracker)` instead of the SDK's `DelegateExecutor`
- [ ] 2.4 Update `build_orchestrator_agent()` in `agent.py` to pass the shared `ReferenceTracker` instance to `DelegateTool.create(tracker=tracker)` when registering the delegate tool

## 3. Update orchestrator system prompt

- [ ] 3.1 In `agent.py` `ORCHESTRATOR_PROMPT`, replace the `classify_text` workflow section with instructions to read the "References found" block from delegation observations
- [ ] 3.2 Update the example workflow in the prompt to show the new flow: delegate → read "References found" block → `mark_followed` → delegate to sub-agent
- [ ] 3.3 Remove references to `classify_text` command from the `track_references` tool usage examples in the prompt

## 4. Tests

- [ ] 4.1 Add unit test: `ReferenceInjectingDelegateExecutor` appends a "References found" block when delegation result contains URLs
- [ ] 4.2 Add unit test: already-followed URLs are excluded from the appended block
- [ ] 4.3 Add unit test: block shows "Maximum reference depth reached" when `can_follow_deeper()` is False
- [ ] 4.4 Add unit test: block shows "(none)" when no URLs are found in the delegation result
- [ ] 4.5 Add unit test: `ReferenceTrackingExecutor` returns an error for `classify_text` command (command no longer supported)

## 5. Verification

- [ ] 5.1 Run `uv run pytest -n auto` — all tests pass
- [ ] 5.2 Run `uv run ruff check .` — no lint errors
- [ ] 5.3 Run `uv run mypy .` — no type errors
- [ ] 5.4 Run a real summarization and confirm `agent-trace.log` no longer contains a `classify_text` action or a 1,000+ line agent action echoing thread content
