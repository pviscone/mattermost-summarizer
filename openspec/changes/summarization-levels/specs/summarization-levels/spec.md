## ADDED Requirements

### Requirement: SummaryLevel enum
The system SHALL define a `SummaryLevel` enum with three values: `brief`, `normal`, and `detailed`. `normal` SHALL be the default.

#### Scenario: Default level when none specified
- **WHEN** no level is specified via CLI flag or config
- **THEN** the system uses `SummaryLevel.NORMAL`

#### Scenario: CLI flag overrides config
- **WHEN** `--level brief` is passed on the CLI and config has `default_level = "normal"`
- **THEN** the system uses `SummaryLevel.BRIEF`

### Requirement: Level-specific result submodels
The system SHALL define three Pydantic result models inheriting from `SummaryResultBase`:
- `BriefSummaryResult`: `level` (brief), `tldr` (str), `action_items` (list[str]), `metadata` (SummaryMeta)
- `NormalSummaryResult`: `level` (normal), `tldr` (str), `key_findings` (list[str]), `narrative` (str), `action_items` (list[str]), `participants` (list[str]), `metadata` (SummaryMeta)
- `DetailedSummaryResult`: all NormalSummaryResult fields plus `open_questions` (list[str]), `context_sources` (list[str]), `metadata` (SummaryMeta)

All three SHALL include a `level: SummaryLevel` field indicating which level produced them.

#### Scenario: Brief result creation
- **WHEN** a summary is produced at brief level
- **THEN** the result is a `BriefSummaryResult` instance with `tldr` and `action_items` populated
- **THEN** accessing `.narrative` on the result raises `AttributeError`

#### Scenario: Normal result creation
- **WHEN** a summary is produced at normal level
- **THEN** the result is a `NormalSummaryResult` with all current `SummaryResult` fields

#### Scenario: Detailed result creation
- **WHEN** a summary is produced at detailed level
- **THEN** the result is a `DetailedSummaryResult` with `open_questions` and `context_sources` in addition to normal fields

### Requirement: Level-aware render_rich
Each result submodel SHALL implement its own `render_rich(console)` method. Brief renders only TL;DR and action items. Normal renders the current full layout. Detailed renders the full layout plus open questions and context sources sections.

#### Scenario: Brief render_rich output
- **WHEN** `render_rich` is called on a `BriefSummaryResult`
- **THEN** output contains "TL;DR" and optionally "ACTION ITEMS"
- **THEN** output does NOT contain "NARRATIVE", "KEY FINDINGS", or "PARTICIPANTS"

#### Scenario: Detailed render_rich includes extra sections
- **WHEN** `render_rich` is called on a `DetailedSummaryResult` with non-empty `open_questions` and `context_sources`
- **THEN** output contains "OPEN QUESTIONS" and "CONTEXT SOURCES" sections

### Requirement: Level-aware __str__
Each result submodel SHALL implement its own `__str__()` method producing plain-text output matching the render_rich section structure for that level.

#### Scenario: Brief __str__ output
- **WHEN** `str()` is called on a `BriefSummaryResult`
- **THEN** output contains "TL;DR" section and optionally "ACTION ITEMS" section
- **THEN** output does NOT contain "NARRATIVE" or "KEY FINDINGS" sections

#### Scenario: Detailed __str__ includes extra sections
- **WHEN** `str()` is called on a `DetailedSummaryResult`
- **THEN** output contains "OPEN QUESTIONS" and "CONTEXT SOURCES" sections when those lists are non-empty

### Requirement: Level-specific finish action schemas
The system SHALL define three finish action Pydantic models inheriting from `SummarizerFinishActionBase`:
- `BriefFinishAction`: `tldr` (str), `action_items` (list[str])
- `NormalFinishAction`: `tldr`, `key_findings`, `narrative`, `action_items`, `participants`
- `DetailedFinishAction`: all Normal fields plus `open_questions` (list[str]), `context_sources` (list[str])

`SummarizerFinishActionBase` SHALL carry shared fields and serve as the `isinstance` target for `_extract_finish_action()`.

#### Scenario: Brief action schema enforcement
- **WHEN** the agent runs at brief level
- **THEN** the finish tool schema exposes only `tldr` and `action_items` fields
- **THEN** the LLM cannot return `narrative` via the finish tool

#### Scenario: Extract finish action via base class
- **WHEN** `_extract_finish_action()` scans conversation events
- **THEN** it identifies finish actions by `isinstance(action, SummarizerFinishActionBase)` regardless of level

### Requirement: Level-specific finish tools
The system SHALL define three `ToolDefinition` subclasses, one per level, all registered under the name `"finish"`. Only the tool matching the current level SHALL be registered per agent run.

#### Scenario: Brief tool registration
- **WHEN** building tools for brief level
- **THEN** the agent receives one finish tool with the `BriefFinishAction` schema registered as `"finish"`

#### Scenario: Normal tool registration
- **WHEN** building tools for normal level
- **THEN** the agent receives one finish tool with the `NormalFinishAction` schema registered as `"finish"`

#### Scenario: No duplicate finish tools
- **WHEN** building tools for any level
- **THEN** exactly one finish tool is registered in the agent's tool list

### Requirement: Level-specific prompt addenda
Each level SHALL define a `USER_MESSAGE_ADDENDUM` string constant containing level-specific instructions for the LLM. The addendum SHALL be appended to the user message alongside the base system prompt.

#### Scenario: Brief addendum content
- **WHEN** building the user message for brief level
- **THEN** the message includes instructions to be minimal, produce only TL;DR and action items, and not fetch external URLs

#### Scenario: Detailed addendum content
- **WHEN** building the user message for detailed level
- **THEN** the message includes instructions to fetch all referenced URLs, be thorough, and list open questions and context sources

#### Scenario: Normal addendum content
- **WHEN** building the user message for normal level
- **THEN** the message includes the current base instructions without additional level-specific guidance

### Requirement: JSON output includes level field
When output format is JSON, the result SHALL include a `level` field with the `SummaryLevel` value (e.g., `"brief"`, `"normal"`, `"detailed"`). The JSON shape SHALL be the natural Pydantic serialization for that level's result model.

#### Scenario: Brief JSON output
- **WHEN** `model_dump_json()` is called on a `BriefSummaryResult`
- **THEN** the JSON contains `"level": "brief"`, `"tldr"`, `"action_items"`, and `"metadata"`
- **THEN** the JSON does NOT contain `"narrative"`, `"key_findings"`, or `"participants"` keys

#### Scenario: Detailed JSON output
- **WHEN** `model_dump_json()` is called on a `DetailedSummaryResult`
- **THEN** the JSON contains `"level": "detailed"`, `"open_questions"`, and `"context_sources"` in addition to normal fields
