## MODIFIED Requirements

### Requirement: Configurable recursion depth
The maximum reference depth SHALL be configurable via the `[summarizer]` TOML section or environment variables.

```toml
[summarizer]
max_reference_depth = 3
```

- A value of 0 SHALL disable recursive following entirely (no external URLs, no root thread file attachments)
- A value of 1 SHALL allow following references from the root thread, but no deeper (depth 1)
- If `max_reference_depth` is explicitly set via configuration (TOML or env var), the system SHALL ALWAYS use that explicit value.
- If `max_reference_depth` is NOT explicitly set via configuration (is `None`), the system SHALL dynamically infer the effective depth based on the requested summary `level`:
  - `brief`: Depth 0
  - `normal`: Depth 1
  - `detailed`: Depth 3

#### Scenario: Custom depth explicitly configured
- **WHEN** `[summarizer] max_reference_depth = 5` is configured
- **AND** the user requests a `brief` summary
- **THEN** the explicit config wins, and the orchestrator follows references up to depth 5

#### Scenario: No explicit depth config, brief level
- **WHEN** `max_reference_depth` is not explicitly set in config
- **AND** the user requests a `brief` summary
- **THEN** the system dynamically sets the effective depth to 0
- **THEN** no external references or file attachments from the root thread are fetched

#### Scenario: No explicit depth config, normal level
- **WHEN** `max_reference_depth` is not explicitly set in config
- **AND** the user requests a `normal` summary (or uses the default level which is normal)
- **THEN** the system dynamically sets the effective depth to 1
- **THEN** references found in the root thread are fetched, but their children are not

#### Scenario: Depth limit prevents infinite recursion
- **WHEN** thread A references B, B references C, C references D, etc. (chain)
- **THEN** the orchestrator stops delegating at effective max_reference_depth
- **THEN** no infinite delegation loop occurs