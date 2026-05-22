## ADDED Requirements

### Requirement: LLM-as-critic for quality evaluation
The system SHALL use an LLM-based critic to evaluate summary quality and enable iterative refinement.

The `SummarizationCritic` class:
- SHALL extend `CriticBase` from the OpenHands SDK
- SHALL evaluate the summary against the original thread content and gathered context
- SHALL return a `CriticResult` with a score (0-1) and feedback message
- SHALL use a separate LLM instance for evaluation (with its own usage_id)

The critic SHALL be attached to the orchestrator agent. When the orchestrator calls finish:
1. The critic evaluates the summary quality
2. If the score is below the threshold, the orchestrator receives feedback and revises
3. This loop repeats up to max_iterations times

#### Scenario: Summary passes quality threshold
- **WHEN** the critic evaluates a summary with score 0.85
- **THEN** the score is above success_threshold (0.7)
- **THEN** the summary is accepted without revision
- **THEN** summarization completes

#### Scenario: Summary fails quality threshold, revision occurs
- **WHEN** the critic evaluates a summary with score 0.55
- **THEN** the score is below success_threshold (0.7)
- **THEN** feedback is generated: "TL;DR misses the key decision about migration"
- **THEN** the orchestrator receives the feedback as a new user message
- **THEN** the orchestrator revises the summary and calls finish again
- **THEN** the critic evaluates the revised summary

### Requirement: Level-specific rubric evaluation
The critic SHALL use a level-specific rubric prompt for evaluation:

**Brief mode rubric**: Evaluate whether the TL;DR is:
- Concise (captures key points without excess detail)
- Complete (all major outcomes captured)
- Appropriately terse (no fluff, no redundant points)

**Normal mode rubric**: Evaluate whether the summary:
- Captures all key findings and decisions
- Has an accurate chronological narrative
- Identifies all action items and follow-ups
- Lists all participants who contributed

**Detailed mode rubric**: Additionally evaluate whether the summary:
- Identifies open questions and uncertainties
- Cites sources for factual claims
- Captures nuanced points and edge cases discussed

#### Scenario: Brief mode rubric applied
- **WHEN** a brief summary is evaluated
- **THEN** the critic uses the brief rubric
- **THEN** the summary is NOT penalized for lacking narrative depth
- **THEN** the score reflects terseness and key point capture

#### Scenario: Detailed mode rubric applied
- **WHEN** a detailed summary is evaluated
- **THEN** the critic uses the detailed rubric
- **THEN** the summary IS evaluated on open questions and source citation
- **THEN** missing open questions result in lower score

### Requirement: Critic feedback format
The critic SHALL return feedback that identifies specific issues:

- **WHAT** is missing or wrong (e.g., "missing action item from thread xyz789")
- **WHY** it matters (e.g., "this was a key decision point mentioned by multiple participants")
- **HOW** to fix it (e.g., "include the migration timeline decision from the thread")

The feedback SHALL be actionable enough for the orchestrator to revise the summary.

#### Scenario: Actionable feedback for missing action items
- **WHEN** the critic evaluates a summary that misses 2 action items
- **THEN** the feedback message identifies which action items are missing
- **THEN** the feedback references where they appear in the thread content
- **THEN** the orchestrator can add the missing items in the revision

### Requirement: Critic evaluation input
The critic SHALL have access to:

1. **Original thread content**: The posts from the root thread (via thread_fetcher results)
2. **Gathered context**: All fetched references (Launchpad bugs, GitHub issues, files, other threads)
3. **Produced summary**: The finish action output (TL;DR, key findings, narrative, action items, participants)

The critic SHALL NOT have access to raw API responses — only the formatted text that sub-agents returned to the orchestrator.

#### Scenario: Critic receives full context for evaluation
- **WHEN** the critic evaluates a summary
- **THEN** it reads the original thread posts from the thread_fetcher result
- **THEN** it reads the bug_researcher result for referenced bug context
- **THEN** it reads the github_researcher result for referenced PR context
- **THEN** it reads the finish action for the produced summary
- **THEN** it evaluates whether the summary captures all this information accurately

### Requirement: Iterative refinement configuration
The critic SHALL support configurable iterative refinement:

```python
class SummarizationCritic(CriticBase):
    iterative_refinement = IterativeRefinementConfig(
        success_threshold=0.7,
        max_iterations=2,
    )
```

- `success_threshold`: Minimum score (0-1) to accept the summary
- `max_iterations`: Maximum revision rounds before giving up

#### Scenario: Max iterations reached without passing threshold
- **WHEN** iteration 1: score 0.55, revision requested
- **WHEN** iteration 2: score 0.60, revision requested
- **WHEN** iteration 3: would exceed max_iterations (2)
- **THEN** the summary is returned as-is (best effort)
- **THEN** a warning or flag indicates quality threshold was not met