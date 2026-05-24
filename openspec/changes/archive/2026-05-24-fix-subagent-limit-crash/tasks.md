## 1. Config Update

- [x] 1.1 Update `max_sub_agents` default in `MattermostSummarizerConfig` (src/mattermost_summarizer/config.py) from 20 to 500.

## 2. Executor Initialization

- [x] 2.1 Ensure `max_children` is passed through properly from config -> orchestrator agent -> `FetchReferenceExecutor` -> `DelegateExecutor`. (This may already be happening but verify tests pass).

## 3. Testing & Verification

- [x] 3.1 Run tests `uv run pytest -n auto` to verify `max_sub_agents` defaults and pass-through.
- [x] 3.2 Update any tests asserting `max_children=20` to `max_children=500`.
