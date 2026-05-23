## MODIFIED Requirements

### Requirement: LLM-driven reference selection
The orchestrator SHALL decide which references to follow based on their relevance to the discussion, using the pre-classified URL list provided in each delegation observation — not by calling a classification tool.

The orchestrator (LLM):
- SHALL read the "References found" block appended to each delegation observation
- SHALL evaluate each listed URL for relevance to the discussion
- SHALL use `track_references(command="is_followed", url="...")` to confirm a URL has not been followed (as a consistency check, since already-followed URLs are filtered from the block by the Python layer)
- SHALL use `track_references(command="mark_followed", url="...")` before delegating to a sub-agent for a URL
- SHALL skip following references that are irrelevant
- SHALL NOT call `track_references(command="classify_text", ...)` — this command no longer exists

#### Scenario: Orchestrator reads pre-classified list and follows relevant URL
- **WHEN** the delegation observation contains a "References found" block listing a GitHub PR
- **THEN** the orchestrator evaluates whether the PR is central to the discussion
- **THEN** if relevant, it calls `track_references(command="mark_followed", url="...")` and delegates to `github_researcher`
- **THEN** it does NOT call `track_references(command="classify_text", ...)`

#### Scenario: Orchestrator skips irrelevant reference from pre-classified list
- **WHEN** the "References found" block lists a URL that is only a passing mention
- **THEN** the orchestrator MAY decide to skip fetching that URL
- **THEN** it does NOT call `mark_followed` for the skipped URL
- **THEN** only relevant references are delegated

#### Scenario: Orchestrator avoids duplicate fetching
- **WHEN** a URL appears in the delegation result but was already followed at a prior depth
- **THEN** it does NOT appear in the "References found" block (filtered by the Python layer)
- **THEN** the orchestrator does not re-delegate to the same URL

## REMOVED Requirements

### Requirement: URL classification for delegation routing (classify_text command)
**Reason**: URL classification now happens in the Python layer (inside `DelegateTool`) before observations reach the LLM. The `classify_text` LLM tool command caused the LLM to echo the entire thread content (~40K tokens) into its action output, permanently inflating the conversation context. The classification capability is preserved in Python via `classify_urls_in_text()`.

**Migration**: The orchestrator prompt no longer instructs the LLM to call `classify_text`. Classified URLs arrive pre-computed in the "References found" block of each delegation observation. Tests that exercised `classify_text` via the LLM tool should be replaced with tests that verify the "References found" block is present in delegation observations.
