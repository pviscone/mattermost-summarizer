## Requirements

### Requirement: Prefetch root Mattermost thread
The system SHALL prefetch the root Mattermost thread defined by the permalink URL before passing the initial user prompt to the orchestrator LLM, ensuring the root thread data is fully present in the prompt.

#### Scenario: Summarization begins
- **WHEN** the `MattermostSummarizer.summarize()` method is called with a valid permalink
- **THEN** it fetches the thread using the `MattermostClient`
- **THEN** it formats the thread text and injects it into the initial user message
- **THEN** the initial message passed to the LLM does not contain the original permalink URL to prevent duplicate fetching

### Requirement: Prevent duplicate agent spawns for root thread
The system SHALL mark the root thread permalink URL as followed in the `ReferenceTracker` before starting the orchestrator LLM to prevent it from autonomously spawning sub-agents for the root URL.

#### Scenario: Reference tracker initialization
- **WHEN** the `ReferenceTracker` is instantiated during summarization setup
- **THEN** the root thread permalink URL is immediately marked as followed at depth 0

### Requirement: Accurately estimate thread length
The system SHALL compute the root thread length directly from the pre-fetched observation rather than scanning LLM event history.

#### Scenario: Summary metadata generation
- **WHEN** the `MattermostSummarizer.summarize()` method finishes and constructs `SummaryMeta`
- **THEN** the `thread_length` metric uses the total replies count from the pre-fetched root thread observation (+1 for the root post itself)
