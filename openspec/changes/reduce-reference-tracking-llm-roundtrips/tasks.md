## 1. Refactor ReferenceTrackingTool

- [ ] 1.1 Add `follow_url` command to `ReferenceTrackingExecutor` in `reference_tracking_tool.py`: atomically run `has_been_followed` check, `can_follow_deeper` check, `mark_followed`, and `increment_depth` under `tracker.lock()`; return distinct results for success / already-followed / depth-exceeded
- [ ] 1.2 Remove `classify_text`, `is_followed`, `can_follow`, `mark_followed`, and `increment_depth` command handlers from `ReferenceTrackingExecutor`
- [ ] 1.3 Update `ReferenceTrackingTool.create()` description string to advertise only `follow_url`, `classify`, and `reset`
- [ ] 1.4 Update `ReferenceTrackingObservation` fields: add `already_followed: bool | None` and `depth_exceeded: bool | None`; remove fields that are no longer populated by any command

## 2. Add Post-Delegation Callback

- [ ] 2.1 In `summarizer.py`, confirm the attribute on `DelegateObservation` that holds result text (read `delegate_tool.py` and check `to_llm_content`)
- [ ] 2.2 Implement `_post_delegation_callback(event, tracker, conv_ref)` closure: detect `DelegateObservation` events, call `classify_urls_in_text(text, tracker)`, format the list, and call `conversation.send_message(...)` if any followable URLs found
- [ ] 2.3 Pass `_post_delegation_callback` (in addition to the existing `_on_finish_callback`) in the `callbacks` list when constructing `LocalConversation`
- [ ] 2.4 Verify callback does NOT fire on non-delegation observations (guard condition)

## 3. Update Orchestrator Prompt

- [ ] 3.1 In `agent.py`, remove `classify_text` instructions from `ORCHESTRATOR_PROMPT`
- [ ] 3.2 Replace the 4-step per-URL protocol with a description of the single `follow_url(url)` call
- [ ] 3.3 Add a note that classified URL lists are provided automatically after each delegation and the LLM should use them to decide relevance

## 4. Update Tests

- [ ] 4.1 In `test_tools.py` (or equivalent), update/replace tests that use the removed commands (`classify_text`, `is_followed`, `can_follow`, `mark_followed`, `increment_depth`)
- [ ] 4.2 Add unit tests for `follow_url`: success path, already-followed path, depth-exceeded path
- [ ] 4.3 Add a unit test for the post-delegation callback: mock a `DelegateObservation` with known URLs, assert the injected message content

## 5. Verification

- [ ] 5.1 Run `uv run ruff check .` and fix any linting issues
- [ ] 5.2 Run `uv run mypy .` and fix any type errors
- [ ] 5.3 Run `uv run pytest -n auto` and confirm all tests pass
