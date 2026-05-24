# Spec: Atomic URL Follow

## Capability

Provide an atomic `follow_url` command on the `track_references` tool that combines URL-already-followed check, depth-limit check, mark-as-followed, and depth-increment into a single operation, eliminating TOCTOU races and reducing LLM round-trips.

## Requirements

### Requirement: Atomic URL follow command
The `track_references` tool SHALL provide a `follow_url(url)` command that atomically checks followability, marks the URL as followed, and increments depth in a single operation.

The command SHALL return one of three outcomes:
- `success` — URL was not previously followed and depth limit not exceeded; URL is now marked followed and depth incremented
- `already_followed` — URL was already followed; no state change
- `depth_exceeded` — maximum depth reached; URL is not marked followed

The operation SHALL execute under the tracker lock to prevent TOCTOU races in concurrent delegation scenarios.

#### Scenario: follow_url succeeds for new URL within depth
- **WHEN** `follow_url` is called with a URL not previously followed and current depth < max_depth
- **THEN** the URL is marked as followed
- **THEN** the depth counter is incremented
- **THEN** the command returns `success`

#### Scenario: follow_url returns already_followed for duplicate
- **WHEN** `follow_url` is called with a URL that has already been followed
- **THEN** no state change occurs
- **THEN** the command returns `already_followed`

#### Scenario: follow_url returns depth_exceeded at max depth
- **WHEN** `follow_url` is called and current depth equals max_depth
- **THEN** the URL is NOT marked as followed
- **THEN** the depth counter is NOT incremented
- **THEN** the command returns `depth_exceeded`

#### Scenario: follow_url is atomic under concurrent calls
- **WHEN** two concurrent callers call `follow_url` with the same URL simultaneously
- **THEN** exactly one returns `success` and one returns `already_followed`
- **THEN** depth is incremented exactly once

#### Note: Depth is per-URL nesting level, not a global counter
Each URL is assigned a depth level when it is pre-registered by `FetchReferenceExecutor`. The root thread is at depth 0. URLs found in its result are pre-registered at depth 1. URLs found in those results are pre-registered at depth 2, and so on.

Sibling URLs discovered at the same nesting level all share the same depth value. Following 10 URLs at depth 1 does NOT consume depth budget — all 10 remain at depth 1. Only traversing deeper (following a URL found *within* one of those results) increments the depth to 2.

`max_reference_depth` therefore limits **nesting depth** (how many hops from the root), not total work. With `max_depth=3`, the system can follow arbitrarily many sibling references at each level, but will not follow references found inside depth-2 results (those would be at depth 3, which equals max_depth and is rejected).

This is distinct from what was originally described (a global total-URL counter). The per-URL nesting model was implemented because it more naturally matches the intent of "how many levels deep should we follow links".