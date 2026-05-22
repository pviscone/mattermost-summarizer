## 1. Levels Package Foundation

- [x] 1.1 Create `levels/__init__.py` with `SummaryLevel` enum (brief, normal, detailed), `AnySummaryResult` type alias, and re-exports of all public types
- [x] 1.2 Create `levels/base.py` with `SummaryResultBase` (level field, metadata, shared render helper for metadata footer), `SummaryMeta` (moved from models.py), `SummarizerFinishActionBase` (shared base with `is_summarizer_finish: Literal[True]`), `SummarizerFinishObservation`, `SummarizerFinishExecutor`

## 2. Brief Level

- [x] 2.1 Create `levels/brief.py` with `BriefFinishAction` (tldr, action_items), `BriefFinishTool`, `BriefSummaryResult` (level, tldr, action_items, metadata), `USER_MESSAGE_ADDENDUM`
- [x] 2.2 Implement `BriefSummaryResult.render_rich()` — TL;DR only, optionally ACTION ITEMS, metadata footer
- [x] 2.3 Implement `BriefSummaryResult.__str__()` — plain-text matching render_rich sections

## 3. Normal Level

- [x] 3.1 Create `levels/normal.py` with `NormalFinishAction` (current SummarizerFinishAction fields), `NormalFinishTool`, `NormalSummaryResult` (current SummaryResult fields + level field), `USER_MESSAGE_ADDENDUM`
- [x] 3.2 Implement `NormalSummaryResult.render_rich()` — current behavior from models.py
- [x] 3.3 Implement `NormalSummaryResult.__str__()` — current behavior from models.py

## 4. Detailed Level

- [x] 4.1 Create `levels/detailed.py` with `DetailedFinishAction` (normal fields + open_questions, context_sources), `DetailedFinishTool`, `DetailedSummaryResult` (normal fields + open_questions, context_sources, level field), `USER_MESSAGE_ADDENDUM`
- [x] 4.2 Implement `DetailedSummaryResult.render_rich()` — normal sections plus OPEN QUESTIONS and CONTEXT SOURCES sections
- [x] 4.3 Implement `DetailedSummaryResult.__str__()` — plain-text matching render_rich sections

## 5. Models Shim & Cleanup

- [x] 5.1 Convert `models.py` to thin shim: keep PostData, PostThread, Channel, UserProfile, ReactionData; re-export SummaryMeta, SummaryResult (= NormalSummaryResult), all level result types from levels/
- [x] 5.2 Remove SummaryResult class and SummaryMeta class definitions from models.py (now in levels/)
- [x] 5.3 Verify backward compatibility: `from mattermost_summarizer.models import SummaryResult, SummaryMeta` still works

## 6. Finish Tool Migration

- [x] 6.1 Delete `tools/finish/` directory entirely
- [x] 6.2 Update `tools/__init__.py`: `build_summarizer_tools()` and `build_mattermost_tools()` take `level: SummaryLevel` parameter and import finish tool directly from `levels/`
- [x] 6.3 Register only the level-matching finish tool under the name `"finish"` in `build_summarizer_tools()`

## 7. Agent & Summarizer Updates

- [x] 7.1 Add `build_user_message(permalink_url, post_id, level)` function to `agent.py` that constructs the user message including the level's `USER_MESSAGE_ADDENDUM`
- [x] 7.2 Update `MattermostSummarizer.summarize()` to accept `level: SummaryLevel = SummaryLevel.NORMAL` parameter
- [x] 7.3 Update `summarize()` to pass level to `build_summarizer_tools()` and `build_user_message()`
- [x] 7.4 Update `_extract_finish_action()` to use `isinstance(action, SummarizerFinishActionBase)` instead of duck-typing
- [x] 7.5 Update `summarize()` return type to `AnySummaryResult`
- [x] 7.6 Update `summarize()` to construct the correct result submodel based on level (extract fields from finish action, build BriefSummaryResult/NormalSummaryResult/DetailedSummaryResult)

## 8. Config & CLI

- [x] 8.1 Add `default_level: SummaryLevel = SummaryLevel.NORMAL` field to `MattermostSummarizerConfig` with env var `MM_SUMMARIZER_DEFAULT_LEVEL`
- [x] 8.2 Update `MattermostSummarizerConfig.from_config()` to parse `[summarizer]` section from TOML
- [x] 8.3 Add `--level` flag to `summarize.py` CLI with choices `brief`, `normal`, `detailed`
- [x] 8.4 Wire CLI `--level` flag to override config `default_level` when passed
- [x] 8.5 Pass resolved level to `summarizer.summarize(url, level=level)`

## 9. Tests

- [x] 9.1 Create `tests/test_levels.py` with tests for SummaryLevel enum, AnySummaryResult type alias, and level module imports
- [x] 9.2 Add BriefSummaryResult creation, render_rich, and __str__ tests
- [x] 9.3 Add NormalSummaryResult tests (verify current behavior preserved)
- [x] 9.4 Add DetailedSummaryResult creation, render_rich, and __str__ tests (including OPEN QUESTIONS and CONTEXT SOURCES sections)
- [x] 9.5 Add finish action schema tests: BriefFinishAction has no narrative field, DetailedFinishAction has open_questions and context_sources fields
- [x] 9.6 Add prompt addendum tests: each level's USER_MESSAGE_ADDENDUM is non-empty and level-appropriate
- [x] 9.7 Add JSON output tests: brief JSON has no narrative key, detailed JSON has open_questions, all have level field
- [x] 9.8 Add config tests: TOML [summarizer] section parsing, env var override, CLI flag override
- [x] 9.9 Update existing `tests/test_models.py`: verify SummaryResult import still works via shim
- [x] 9.10 Update existing `tests/test_tools.py`: move/update finish observation tests to reference levels/base.py

## 10. Linting & Type Checking

- [x] 10.1 Run `uv run ruff check .` and fix all issues
- [x] 10.2 Run `uv run mypy .` and fix all type errors (especially union return types, level parameter additions)
- [x] 10.3 Run `uv run pyright` and fix all issues
- [x] 10.4 Run `uv run pytest` and ensure all tests pass