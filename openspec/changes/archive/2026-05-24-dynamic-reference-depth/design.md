## Context

Currently, the summarizer delegates reference fetching to sub-agents (via `FetchReferenceExecutor` and `ReferenceTracker`). The depth of recursion is hardcoded to a default of 3 in the `MattermostSummarizerConfig`, or overridden via TOML/env vars.
When users request a `brief` summary, they want a fast, shallow overview. However, the system still crawls up to 3 levels deep if references exist, wasting LLM tokens and execution time on context that won't make it into the final brief output.

## Goals / Non-Goals

**Goals:**
- Dynamically adjust the context-gathering depth based on the requested summarization level when no explicit config is provided.
- Maintain strict backward compatibility for users who explicitly configure `max_reference_depth`.
- Ensure the logic for deriving the depth is cleanly separated from the configuration loading.

**Non-Goals:**
- Adding a new CLI flag specifically for `--depth`. We are inferring depth from the existing `--level` flag.
- Modifying how `FetchReferenceExecutor` or `ReferenceTracker` enforce depth; we are only changing how they are initialized.

## Decisions

**1. Placement of the logic:**
- **Decision:** Place the logic for deriving the effective depth inside `MattermostSummarizer.summarize()` rather than inside a Pydantic `model_validator` in the config class.
- **Rationale:** The CLI can override the summarization level at runtime (e.g. `uv run summarize.py <url> --level brief`). If the logic lived in the config parser, it wouldn't know about the CLI override. Placing it in `summarize()` ensures it uses the *effective* level (either CLI-provided or config-default).

**2. Nullable Configuration Value:**
- **Decision:** Change `MattermostSummarizerConfig.max_reference_depth` from `int = Field(default=3)` to `int | None = Field(default=None)`.
- **Rationale:** This allows the code to unambiguously differentiate between "the user explicitly set depth=0" and "the user didn't set a depth, so use the default for the current level".

**3. The Default Depth Mapping:**
- **Decision:** Use a strict mapping: `brief` -> 0, `normal` -> 1, `detailed` -> 3.
- **Rationale:** 
  - `brief` aims for speed; zero external fetching (including file attachments) ensures the fastest possible path.
  - `normal` provides context from direct references in the root thread (depth 1).
  - `detailed` allows deep diving (depth 3) to thoroughly understand a complex issue.

**4. Keeping the "References found" block at Depth 0:**
- **Decision:** Do not modify the prompt injection to hide un-followed URLs. The LLM will still see the URLs and the message "Maximum reference depth reached. Do not follow further references."
- **Rationale:** It's important for the LLM to know that context exists but was intentionally excluded, rather than thinking the root thread is entirely isolated.

## Risks / Trade-offs

- **Risk:** Users requesting a `brief` summary on a thread that consists solely of a link to a GitHub PR will get a very sparse/poor summary because the depth is 0.
  - **Mitigation:** Document this behavior. If they want brief output but deep context, they can explicitly set `max_reference_depth = 3` in their config, which overrides the dynamic default.
- **Risk:** At depth 0, file attachments attached directly to the root thread (like `logs.txt`) are not fetched.
  - **Mitigation:** Accepted trade-off. `brief` means fast and shallow. Parsing large log files contradicts this.