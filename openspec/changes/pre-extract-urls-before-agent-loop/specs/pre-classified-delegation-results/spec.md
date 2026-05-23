## ADDED Requirements

### Requirement: Delegation observations include pre-classified URL list
After each successful delegation round, the system SHALL automatically extract and classify URLs from the delegation result text and append a structured reference block to the observation before it is delivered to the orchestrator LLM.

The appended block:
- SHALL list each unique, not-yet-followed URL with its reference type and target sub-agent
- SHALL include the current depth and whether further following is permitted
- SHALL omit URLs already marked as followed by the `ReferenceTracker`
- SHALL be appended even when no URLs are found (indicating an empty references block)

#### Scenario: Delegation result contains actionable URLs
- **WHEN** a `delegate` observation is returned containing GitHub and Launchpad URLs
- **THEN** the observation text ends with a "--- References found ---" block
- **THEN** each URL is listed with its type and target sub-agent (e.g., `github_issue → github_researcher`)
- **THEN** the current depth and max depth are shown
- **WHEN** the orchestrator LLM reads the observation
- **THEN** it can immediately use the pre-classified list without calling `classify_text`

#### Scenario: Delegation result contains no URLs
- **WHEN** a `delegate` observation is returned with no recognizable URLs in the result text
- **THEN** the observation text ends with "--- References found ---\n(none)"
- **THEN** the orchestrator LLM does not need to call any classification tool

#### Scenario: Already-followed URLs are excluded from the block
- **WHEN** a delegation result contains a URL that was previously marked as followed
- **THEN** that URL does NOT appear in the "References found" block
- **THEN** the LLM is not prompted to follow the same URL again

#### Scenario: Max depth reached
- **WHEN** `ReferenceTracker.can_follow_deeper()` returns False at the time of observation construction
- **THEN** the "References found" block still lists the URLs found
- **THEN** the block states "Maximum reference depth reached — do not follow further references"
- **THEN** the orchestrator LLM does not delegate to sub-agents for those URLs
