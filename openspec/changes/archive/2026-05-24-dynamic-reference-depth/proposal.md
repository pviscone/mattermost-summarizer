## Why

Currently, the `max_reference_depth` config is a static default of 3 regardless of the summary level. This means a "brief" summary request will still fetch deep context up to 3 levels deep, consuming time and tokens, even though the output is meant to be short. By coupling the summary `level` (brief, normal, detailed) to the `max_reference_depth`, we align the amount of context fetched with the requested detail of the summary, saving execution time and LLM costs for shorter summaries.

## What Changes

- Modify `max_reference_depth` in `MattermostSummarizerConfig` to be optional (`int | None`).
- If `max_reference_depth` is explicitly set via TOML or Environment variables, that value is always honored.
- If `max_reference_depth` is NOT explicitly set, its default value is dynamically determined by the `level` of the summarization request:
  - `brief`: Depth 0 (no external URLs, no file attachments fetched)
  - `normal`: Depth 1 (fetch root thread references, but don't follow their children)
  - `detailed`: Depth 3 (fetch up to 3 levels of nested references)
- Inject the dynamic depth into the `ReferenceTracker` via the `summarize` function in `summarizer.py`.
- **BREAKING**: For `brief` summaries, root thread file attachments (e.g. `logs.txt`) will no longer be fetched, as the effective depth is 0.

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `recursive-reference-following`: The configurable recursion depth requirement is changing to include dynamic defaults based on summary level.

## Impact

- `src/mattermost_summarizer/config.py`: `MattermostSummarizerConfig.max_reference_depth` becomes `int | None` with `default=None`.
- `src/mattermost_summarizer/summarizer.py`: `summarize` method will contain the logic to calculate `effective_depth` and pass it to `ReferenceTracker`.
- Test cases around configuration precedence and ReferenceTracker initialization will need to be updated or added.