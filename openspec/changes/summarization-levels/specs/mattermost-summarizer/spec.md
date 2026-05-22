## ADDED Requirements

### Requirement: Summarizer config section
The TOML config SHALL support a `[summarizer]` section with a `default_level` field (default: `"normal"`). The env var `MM_SUMMARIZER_DEFAULT_LEVEL` SHALL override the TOML value. The CLI `--level` flag SHALL override both.

#### Scenario: TOML default_level
- **WHEN** the TOML config contains `[summarizer]` with `default_level = "brief"`
- **THEN** the config loads `default_level` as `SummaryLevel.BRIEF`

#### Scenario: Env var override
- **WHEN** `MM_SUMMARIZER_DEFAULT_LEVEL=detailed` is set and TOML has `default_level = "brief"`
- **THEN** the config resolves `default_level` as `SummaryLevel.DETAILED`

#### Scenario: CLI flag override
- **WHEN** `--level normal` is passed and config has `default_level = "brief"`
- **THEN** the summarizer uses `SummaryLevel.NORMAL`

### Requirement: CLI --level flag
The `summarize.py` CLI SHALL accept a `--level` flag with choices `brief`, `normal`, `detailed`. If omitted, the config `default_level` is used.

#### Scenario: Level flag on CLI
- **WHEN** `summarize.py <url> --level brief` is run
- **THEN** the summarizer produces a `BriefSummaryResult`

#### Scenario: No level flag, no config
- **WHEN** `summarize.py <url>` is run and no `[summarizer]` section exists in config
- **THEN** the summarizer uses `SummaryLevel.NORMAL` (default)

## MODIFIED Requirements

### Requirement: Agent-based Summarization
The system SHALL use the OpenHands Software Agent SDK to perform summarization.
- Agent SHALL have access to FetchThread, GetUserProfile, FetchChannel, and finish tools
- Agent SHALL use a reasoning loop (not single-shot)
- Agent SHALL call the finish tool with structured output when satisfied
- The finish tool schema SHALL vary based on the selected summarization level
- The user message SHALL include level-specific instructions via a prompt addendum

#### Scenario: Brief level agent setup
- **WHEN** summarization is requested at brief level
- **THEN** the agent receives a finish tool with `BriefFinishAction` schema
- **THEN** the user message includes the brief-level addendum

#### Scenario: Detailed level agent setup
- **WHEN** summarization is requested at detailed level
- **THEN** the agent receives a finish tool with `DetailedFinishAction` schema
- **THEN** the user message includes the detailed-level addendum

### Requirement: Stop Condition
The system SHALL use the finish tool as the primary stop condition.
- FinishAction SHALL accept fields as defined by the selected summarization level's finish action schema
- StuckDetector SHALL be enabled as a safety net
- If stuck is detected, the system SHALL return a partial result or raise an error
- `_extract_finish_action()` SHALL identify finish actions via `isinstance(action, SummarizerFinishActionBase)`

#### Scenario: Extracting brief finish action
- **WHEN** a brief-level agent run completes with a `BriefFinishAction`
- **THEN** `_extract_finish_action()` returns the action via base class isinstance check

#### Scenario: Extracting detailed finish action
- **WHEN** a detailed-level agent run completes with a `DetailedFinishAction`
- **THEN** `_extract_finish_action()` returns the action via base class isinstance check

### Requirement: TL;DR Output
The system SHALL produce a bullet-point TL;DR capturing key outcomes and decisions.
- For `brief` level: 2-3 bullet points
- For `normal` level: 3-5 bullet points
- For `detailed` level: 3-5 bullet points

#### Scenario: Brief TL;DR length
- **WHEN** a summary is produced at brief level
- **THEN** the TL;DR contains 2-3 bullet points

#### Scenario: Normal TL;DR length
- **WHEN** a summary is produced at normal level
- **THEN** the TL;DR contains 3-5 bullet points

### Requirement: Narrative Output
The system SHALL produce a chronological narrative describing who said what and how the discussion evolved. This requirement applies to `normal` and `detailed` levels only. `brief` level SHALL NOT produce a narrative.

#### Scenario: Brief level has no narrative
- **WHEN** a summary is produced at brief level
- **THEN** the result has no `narrative` field

#### Scenario: Normal level produces narrative
- **WHEN** a summary is produced at normal level
- **THEN** the result contains a `narrative` field with a chronological walkthrough

#### Scenario: Detailed level produces deeper narrative
- **WHEN** a summary is produced at detailed level
- **THEN** the result contains a `narrative` field noting individual contributions

### Requirement: Action Items
The system SHALL extract action items, decisions, and follow-ups mentioned in the thread. This applies to all three levels.

#### Scenario: Brief level action items
- **WHEN** a summary is produced at brief level
- **THEN** the result includes `action_items` if any were identified

#### Scenario: Normal and detailed action items
- **WHEN** a summary is produced at normal or detailed level
- **THEN** the result includes `action_items` as part of the full output structure

### Requirement: Participants
The system SHALL list all participants who contributed substantively to the thread. This applies to `normal` and `detailed` levels only. `brief` level SHALL NOT list participants.

#### Scenario: Brief level has no participants
- **WHEN** a summary is produced at brief level
- **THEN** the result has no `participants` field

#### Scenario: Normal level lists participants
- **WHEN** a summary is produced at normal level
- **THEN** the result includes a `participants` list

### Requirement: Metadata
The system SHALL include metadata at the bottom of the output: thread length, token stats, model used, duration. This applies to all three levels. The metadata format and rules remain unchanged from the existing spec.

#### Scenario: Brief level metadata
- **WHEN** a brief summary is rendered
- **THEN** the metadata footer is rendered identically to the current format

#### Scenario: Detailed level metadata
- **WHEN** a detailed summary is rendered
- **THEN** the metadata footer is rendered identically to the current format
