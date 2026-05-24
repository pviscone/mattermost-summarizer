## Context

The `DelegateExecutor` in the OpenHands SDK has a default `max_children` limit of 5. Our `FetchReferenceExecutor` spawns a brand-new sub-agent for every referenced URL encountered in a Mattermost thread to ensure clean context windows for the LLM. 
When a thread references multiple URLs (e.g. 4 GitHub PRs), the system hits the limit of 5 (`thread_fetcher` + 4 `github_researcher`s) and crashes with "Failed to spawn sub-agent: Cannot spawn 1 agents. Already have 5, max is 5".

We previously added a `max_sub_agents` parameter to our configuration (defaulting to 20), but the `FetchReferenceExecutor` currently might not be using it correctly, or we need to increase it further to ensure it never gets hit under normal recursive reference following depths.

## Goals / Non-Goals

**Goals:**
- Eliminate the "Failed to spawn sub-agent" error during normal recursive reference following.
- Keep agent contexts clean by continuing to spawn a fresh sub-agent per URL instead of reusing agents.

**Non-Goals:**
- We are explicitly NOT implementing a sub-agent connection pool or reusing sub-agent instances. Agent reuse causes context buildup (LLM context window fills with multiple PRs) which degrades reasoning quality and increases token cost.

## Decisions

- **Decision: Increase `max_sub_agents` default to 500.**
  - **Rationale:** Since we spawn a fresh agent per URL, we just need a sufficiently high ceiling so that we never hit the `DelegateExecutor` hard limit before our own recursive depth limits (e.g., `max_reference_depth=3`) naturally stop the URL fetching.
  - **Alternatives Considered:** 
    - *Agent Pooling/Reuse:* Reusing one `github_researcher` for all GitHub URLs. Rejected due to LLM context buildup and the need for complex locking inside `FetchReferenceExecutor` since `LocalConversation` is not thread-safe.

- **Decision: Ensure `max_children` is properly piped from config to `DelegateExecutor`.**
  - **Rationale:** The `FetchReferenceExecutor` is currently initialized with `max_children=max_sub_agents` (from config), but we must ensure the config default is updated to 500 and the SDK's `DelegateExecutor` receives it.

## Risks / Trade-offs

- [Risk] Memory or resource exhaustion from spawning 500 agents. → Mitigation: We won't actually spawn 500 agents. The `ReferenceTracker` limits recursion depth, and the LLM Orchestrator decides to follow typically 3-5 links. The 500 limit is a safety ceiling to appease `DelegateExecutor`, not a target we expect to reach. OpenHands `LocalConversation` objects are lightweight when not actively executing.
