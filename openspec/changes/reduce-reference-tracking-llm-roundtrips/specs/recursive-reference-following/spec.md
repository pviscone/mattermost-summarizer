## MODIFIED Requirements

### Requirement: LLM-driven reference selection
The orchestrator SHALL decide which references to follow based on their relevance to the discussion, not following all references indiscriminately.

The orchestrator (LLM):
- SHALL evaluate each URL provided in the post-delegation classification message
- SHALL determine whether the reference is central to the discussion or a passing mention
- SHALL skip following references that are irrelevant
- SHALL call `follow_url(url)` once per URL it decides to follow; the system handles cycle detection and depth tracking atomically

#### Scenario: Orchestrator skips irrelevant reference
- **WHEN** the post-delegation message lists a GitHub URL but the issue is not discussed further
- **THEN** the orchestrator MAY decide to skip calling `follow_url` for that URL
- **THEN** only relevant references are delegated

#### Scenario: Orchestrator avoids duplicate fetching
- **WHEN** a URL appears in classification messages at multiple depths
- **THEN** the orchestrator calls `follow_url` for the URL
- **THEN** `follow_url` returns `already_followed`
- **THEN** the orchestrator does NOT re-delegate to that URL

## REMOVED Requirements

### Requirement: URL classification for delegation routing (tool-based)
**Reason**: URL classification is now performed automatically by the post-delegation callback. The orchestrator no longer calls `classify_text` via `track_references`.
**Migration**: No action needed. Classified URL lists are injected automatically after each delegation.
