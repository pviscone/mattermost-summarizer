## 1. Setup and Tool Invocation

- [ ] 1.1 In `src/mattermost_summarizer/summarizer.py`, import `FetchThreadExecutor` and `FetchThreadAction` from `mattermost_summarizer.tools.fetch_thread.impl`.
- [ ] 1.2 Inside `MattermostSummarizer.summarize()`, immediately after initializing the `MattermostClient`, instantiate `FetchThreadExecutor(client)`.
- [ ] 1.3 Call the executor with `FetchThreadAction(post_id=post_id)` to retrieve the root thread.
- [ ] 1.4 Add error handling: if `fetch_obs.error` is populated, raise a `ThreadNotFoundError` or `AgentStuckError` containing the error message.

## 2. Prompt Injection and Tracker Updates

- [ ] 2.1 Extract the formatted thread text from `fetch_obs.to_llm_content` (join by newlines).
- [ ] 2.2 Modify the initial user `message` definition to include the formatted thread text.
- [ ] 2.3 Remove the `{permalink_url}` from the initial user `message` definition to prevent the LLM's `ReferenceTracker` from seeing it.
- [ ] 2.4 Immediately after instantiating `ReferenceTracker`, call `tracker.mark_followed(permalink_url, 0)` to register the root thread as visited.

## 3. Metadata Length Fixes

- [ ] 3.1 Extract the root thread length from the observation (`int(fetch_obs.total_replies) + 1`) and store it in a variable (e.g. `root_thread_length`).
- [ ] 3.2 Update the `SummaryMeta` initialization to use `root_thread_length` instead of calling `_estimate_thread_length(conversation)`.
- [ ] 3.3 Delete the unused `_estimate_thread_length` function from `src/mattermost_summarizer/summarizer.py`.

## 4. Verification and Testing

- [ ] 4.1 Run tests using `uv run pytest -n auto` to ensure no tests break.
- [ ] 4.2 Validate via type checkers (`uv run mypy .` and `uv run pyright`) and linter (`uv run ruff check .`).
