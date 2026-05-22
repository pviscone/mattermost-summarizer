# Spec: Summarization Critic Configuration

## Capability

Configure the LLM critic for iterative summary quality evaluation, including enable/disable, quality threshold, and maximum revision iterations.

## Requirements

### Requirement: Critic configuration section
The system SHALL support critic configuration via the `[summarizer]` TOML section.

The following fields SHALL be configurable:
- `critic_enabled`: Whether iterative refinement is enabled (default: true)
- `critic_threshold`: Quality threshold 0-1 to accept the summary (default: 0.7)
- `critic_max_iterations`: Maximum revision rounds before giving up (default: 2)

```toml
[summarizer]
default_level = "normal"
max_reference_depth = 3
critic_enabled = true
critic_threshold = 0.7
critic_max_iterations = 2
```

#### Scenario: Critic disabled via config
- **WHEN** `[summarizer] critic_enabled = false`
- **THEN** no iterative refinement occurs
- **THEN** summaries are produced without quality evaluation
- **THEN** token cost is reduced by skipping critic LLM calls

#### Scenario: Custom critic threshold
- **WHEN** `[summarizer] critic_threshold = 0.85`
- **THEN** only summaries scoring 0.85+ are accepted without revision
- **THEN** lower-scoring summaries trigger revision rounds

### Requirement: Environment variable override for critic settings
The critic settings SHALL be overridable via environment variables with the `MM_` prefix.

| TOML field | Environment variable |
|-----------|---------------------|
| `critic_enabled` | `MM_CRITIC_ENABLED` |
| `critic_threshold` | `MM_CRITIC_THRESHOLD` |
| `critic_max_iterations` | `MM_CRITIC_MAX_ITERATIONS` |

#### Scenario: Critic threshold via env var
- **WHEN** TOML has `critic_threshold = 0.7` but env has `MM_CRITIC_THRESHOLD=0.9`
- **THEN** the environment variable value (0.9) takes precedence

### Requirement: Default critic configuration
The system SHALL use sensible defaults when critic settings are not explicitly configured:

- `critic_enabled` defaults to `true`
- `critic_threshold` defaults to `0.7` (70% quality score)
- `critic_max_iterations` defaults to `2` (up to 2 revision rounds)

#### Scenario: Default values when no config provided
- **WHEN** no `[summarizer]` section exists in the TOML
- **THEN** critic is enabled with threshold 0.7 and max 2 iterations
- **THEN** environment variables can still override if set