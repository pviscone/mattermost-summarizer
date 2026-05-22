## 1. Config

- [x] 1.1 Add optional `github_token: SecretStr | None` field to `MattermostSummarizerConfig`
- [x] 1.2 Add `[github]` TOML section parsing in `MattermostSummarizerConfig.from_config()`
- [x] 1.3 Document `github_token` in config docstring and example TOML comment

## 2. FetchFile Tool

- [x] 2.1 Create `src/mattermost_summarizer/tools/fetch_file/` directory with `__init__.py` and `impl.py`
- [x] 2.2 Implement `FetchFileAction` (input: `file_id: str`) and `FetchFileObservation` (fields: `content`, `is_binary`, `mime_type`, `error`)
- [x] 2.3 Implement `FetchFileExecutor` using `MattermostClient` to call `GET /api/v4/files/{file_id}`; detect binary via `Content-Type` header
- [x] 2.4 Implement `FetchFileTool` with `create()` classmethod following existing tool pattern
- [x] 2.5 Export `FetchFileTool` from `tools/__init__.py` and wire into `build_mattermost_tools()`
- [x] 2.6 Write unit tests for `FetchFileExecutor`: text file, binary file, not-found cases

## 3. FetchLaunchpadBug Tool

- [x] 3.1 Create `src/mattermost_summarizer/tools/fetch_launchpad_bug/` directory with `__init__.py` and `impl.py`
- [x] 3.2 Implement `FetchLaunchpadBugAction` (input: `bug_url_or_id: str`) and `FetchLaunchpadBugObservation` (fields: title, description, status, importance, tags, comments, total_comments, error)
- [x] 3.3 Implement `FetchLaunchpadBugExecutor` using `httpx.Client`; parse URL or bare ID; call Launchpad REST API v1; fetch comments from `messages_collection_link`; cap at 50 comments
- [x] 3.4 Implement `FetchLaunchpadBugTool` with `create()` classmethod
- [x] 3.5 Export `FetchLaunchpadBugTool` from `tools/__init__.py` and wire into `build_summarizer_tools()`
- [x] 3.6 Write unit tests for `FetchLaunchpadBugExecutor`: by URL, by ID, truncated comments, not-found/private cases

## 4. FetchGitHubIssue Tool

- [x] 4.1 Create `src/mattermost_summarizer/tools/fetch_github_issue/` directory with `__init__.py` and `impl.py`
- [x] 4.2 Implement `FetchGitHubIssueAction` (input: `url: str`) and `FetchGitHubIssueObservation` (fields: title, body, state, labels, assignees, author, created_at, updated_at, comments, total_comments, is_pull_request, review_comments, merge_status, error)
- [x] 4.3 Implement `FetchGitHubIssueExecutor` using `httpx.Client`; parse owner/repo/number from URL; call GitHub REST API v3; detect PR vs issue; fetch review comments for PRs; cap comments at 50; handle 403/429 rate limit with clear message
- [x] 4.4 Implement `FetchGitHubIssueTool` with `create(github_token=None)` classmethod
- [x] 4.5 Export `FetchGitHubIssueTool` from `tools/__init__.py` and update `build_summarizer_tools()` to pass `github_token`
- [x] 4.6 Write unit tests for `FetchGitHubIssueExecutor`: issue, PR, rate-limited, not-found cases

## 5. Agent Wiring

- [x] 5.1 Update `build_summarizer_agent()` / `build_mattermost_tools()` in `agent.py` / `tools/__init__.py` to accept and pass `github_token`
- [x] 5.2 Update `MattermostSummarizer.summarize()` in `summarizer.py` to pass `config.github_token` when constructing tools
- [x] 5.3 Update system prompt in `agent.py` to instruct the agent to follow Mattermost permalinks, Launchpad bug URLs, and GitHub issue/PR URLs found in threads
- [x] 5.4 Run `uv run ruff check .` and `uv run mypy .` — fix any issues (ruff: pass; mypy: 2 pre-existing errors in summarizer.py unrelated to this change)
- [x] 5.5 Run `uv run pytest` — confirm all tests pass (54/54 tests pass, including 8 new tool tests)
