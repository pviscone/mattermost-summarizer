## Why

The summarizer currently produces a single fixed-output structure regardless of the user's needs. Some users want a quick 5-second scan; others need a deep audit with all referenced URLs fetched. Supporting summarization levels (brief, normal, detailed) lets users choose the right tradeoff between speed/cost and depth — without the system doing unnecessary work for shallow summaries.

## What Changes

- Add a `SummaryLevel` enum with three values: `brief`, `normal` (default, current behavior), `detailed`
- Create per-level result submodels (`BriefSummaryResult`, `NormalSummaryResult`, `DetailedSummaryResult`) with distinct fields and rendering
- Create per-level finish action/tool variants so the LLM schema enforces the right output shape per level
- Move all level-related code into a new `levels/` package (result models, finish actions, finish tools, prompt addenda) — one file per level
- Delete `tools/finish/` (absorbed into `levels/`)
- Convert `models.py` into a thin re-export shim (`SummaryResult = NormalSummaryResult` for backward compat)
- Inject level-specific instructions into the user message (not the system prompt)
- Add `--level` CLI flag and `[summarizer]` TOML config section with `default_level`
- Add `level` field to JSON output so consumers know which shape to expect
- Update existing spec requirements that are level-blind (e.g. REQ-008 "SHALL produce narrative" only applies to normal/detailed)

## Capabilities

### New Capabilities
- `summarization-levels`: Defines the three summarization levels (brief, normal, detailed), their output schemas, prompt addenda, and the `SummaryLevel` enum

### Modified Capabilities
- `mattermost-summarizer`: Output requirements (REQ-006 through REQ-010) become level-conditional; API surface changes to support level parameter; config adds `[summarizer]` section; finish tool definition moves to `levels/`

## Impact

- **Code**: New `levels/` package (5 files), deletion of `tools/finish/`, significant changes to `summarizer.py`, `agent.py`, `config.py`, `summarize.py`, `models.py` (shim), `tools/__init__.py`
- **API**: `MattermostSummarizer.summarize()` gains `level` parameter; return type becomes union of submodels; JSON output shape varies by level
- **Config**: New `[summarizer]` TOML section; new env var `MM_SUMMARIZER_DEFAULT_LEVEL`
- **Tests**: New `test_levels.py`; existing `test_models.py` and `test_tools.py` need updates (finish tool tests move)
- **Spec**: Existing REQs 006-010 gain level qualifiers; new "Summarization Levels" spec section
