## Why

The Mattermost Summarizer currently crashes with "Failed to spawn sub-agent: Cannot spawn X agents. Already have Y agents, maximum is Z" when fetching long threads with many URLs. This happens because the orchestrator spawns a new sub-agent for every referenced URL (GitHub PRs, Launchpad bugs, etc.), and the OpenHands `DelegateExecutor` has a default hard limit of `max_children=5`. Because OpenHands `DelegateExecutor` retains all spawned agents in memory and there's no way to evict them, we easily exhaust this pool during moderate reference following. We need to raise this limit significantly so the summarization reliably completes.

## What Changes

- Increase the `max_sub_agents` default configuration value to a very high limit (e.g. 500) to serve purely as an absolute safety ceiling, effectively preventing the `max_children` error under normal operation.
- No changes to agent reuse logic: we will continue spawning fresh sub-agents for each URL to ensure clean context windows, preventing LLM confusion that arises from mixed multi-PR histories.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `orchestrator-agent`: Increase the safe ceiling for max sub-agents to avoid spurious failures while preventing infinite recursive runaway.

## Impact

- **Configuration:** `max_sub_agents` default value changes in `MattermostSummarizerConfig` (and `mattermost-summarizer.toml` examples).
- **Execution:** Resolves intermittent crash errors on deeply-referenced threads.
