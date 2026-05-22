## Context

The Mattermost summarizer currently produces a single fixed output structure: TL;DR, key findings, narrative, action items, and participants. There is no way to control the depth or cost of summarization. Users who want a quick scan get the same expensive output as users who need a full audit trail.

The system uses the OpenHands SDK's agent pattern: a system prompt + user message drives an LLM, which calls a `finish` tool with structured output. The `SummarizerFinishAction` schema defines what fields the LLM must fill in. The `SummaryResult` Pydantic model defines the output shape and rendering.

Current prompt architecture: the system prompt is appended to the user message (line 107-109 of `summarizer.py`), so all instructions flow through the user turn. The finish tool is registered globally under the name `"finish"` with a single action schema.

## Goals / Non-Goals

**Goals:**
- Support three summarization levels: brief (2-3 bullets + action items), normal (current behavior), detailed (full + open questions + sources)
- Per-level finish tool schemas that enforce output shape at the LLM boundary
- Per-level result submodels with level-aware rendering
- Level-specific prompt addenda injected into the user message
- CLI `--level` flag and TOML `[summarizer]` config section for default level
- Co-locate all level definitions (action, result, tool, prompt) in a `levels/` package
- Backward compatibility via `models.py` shim (`SummaryResult = NormalSummaryResult`)

**Non-Goals:**
- Custom/user-defined levels (extensibility is structural, but no plugin system)
- Changing the system prompt architecture (system prompt stays appended to user message)
- Changing how the OpenHands SDK agent/conversation works
- Per-field token budgets or length limits per level
- Streaming or partial results per level

## Decisions

### D1: Submodels over a single model with level-gated fields

**Decision**: Use separate Pydantic models per level (`BriefSummaryResult`, `NormalSummaryResult`, `DetailedSummaryResult`) with a common base class, rather than one model with optional fields gated by a `level` field.

**Rationale**: Submodels provide type safety — you cannot accidentally access `result.narrative` on a `BriefSummaryResult`. Each model owns its own `render_rich()` and `__str__()`. The union type `AnySummaryResult` makes the return type explicit.

**Alternatives considered**:
- Single model with level field: simpler return type, but no compile-time field safety; render_rich would need `if self.level == ...` dispatch
- Duck-typing only: what we have now, doesn't scale to different shapes

### D2: Per-level finish tool variants with same registration name

**Decision**: Three `FinishAction`/`FinishTool` pairs (one per level), all registered under the name `"finish"`. Only the matching level's tool is registered per run.

**Rationale**: The LLM always sees one tool called `finish` with the schema matching the selected level. This means prompts don't need level-specific tool names — the LLM just calls `finish`. The schema itself enforces what fields are required (brief has no `narrative` field, so the LLM physically can't return one).

**Alternatives considered**:
- Distinct names (`finish_brief`, `finish_detailed`): more explicit, but prompts become level-coupled and harder to maintain
- Single action with all fields optional: no schema enforcement, LLM may fill in unnecessary fields

### D3: User message injection for level instructions

**Decision**: Level-specific instructions are appended to the user message (alongside the existing system prompt), not embedded in the system prompt constant.

**Rationale**: The system prompt defines agent identity ("you are a summarizer"). The level is task context ("summarize this thread at brief level"). The code already appends the system prompt to the user message, so this pattern is established. A `build_user_message(permalink, post_id, level)` function constructs the full user message including the level addendum.

### D4: `levels/` package absorbs `tools/finish/`

**Decision**: Delete `tools/finish/` entirely. All finish-related code (action, observation, executor, tool) moves to `levels/`. `build_summarizer_tools()` imports finish tools directly from `levels/`.

**Rationale**: The finish tool is conceptually a *summarization output* concern, not a *Mattermost data fetching* concern. Co-locating it with its level definition means adding a new level touches one file. The `tools/` directory remains for Mattermost API tools only.

### D5: `models.py` becomes a thin re-export shim

**Decision**: Move `SummaryMeta` and all result models to `levels/`. `models.py` keeps `PostData`, `PostThread`, `Channel`, `UserProfile`, `ReactionData` and re-exports `SummaryMeta`, `SummaryResult` (= `NormalSummaryResult`), and all level result types.

**Rationale**: Backward compatibility — existing `from mattermost_summarizer.models import SummaryResult` still works. The shim is cheap to maintain.

### D6: `SummaryMeta` moves to `levels/base.py`

**Decision**: `SummaryMeta` lives alongside `SummaryResultBase` in `levels/base.py` and is re-exported from `models.py`.

**Rationale**: `SummaryMeta` is part of the result model hierarchy. It belongs with the result base class, not with `PostData` and `Channel` which are Mattermost data models.

### D7: New `[summarizer]` TOML config section

**Decision**: Add a `[summarizer]` section with `default_level = "normal"`. Env var: `MM_SUMMARIZER_DEFAULT_LEVEL`.

**Rationale**: Level is a summarizer behavior setting, not a Mattermost connection or LLM provider concern. A dedicated section avoids semantic stretching and leaves room for future summarizer settings (max iterations, custom prompts, etc.).

### D8: `level` field in JSON output

**Decision**: Add a `level: SummaryLevel` field to `SummaryResultBase` so JSON output includes the level name.

**Rationale**: JSON consumers need to know which shape to expect. A `level` field at the top of the JSON is the clearest signal. The rest of the shape is the natural Pydantic serialization for that level's model.

### D9: Common base class for finish actions

**Decision**: `SummarizerFinishActionBase` with a sentinel `is_summarizer_finish: Literal[True]` and shared fields. `_extract_finish_action()` checks `isinstance(action, SummarizerFinishActionBase)`.

**Rationale**: The current duck-typing approach (`hasattr(action, 'tldr') and hasattr(action, 'narrative')`) breaks for brief mode which has no `narrative`. A base class gives a single `isinstance` target and a place for shared fields like `action_items`.

## Risks / Trade-offs

- **[Breaking JSON shape for brief/detailed]** → Consumers parsing JSON output may expect `narrative` to always exist. Mitigation: the `level` field signals the shape; brief mode never had `narrative` so there's no data to miss. Document the level-dependent shape.

- **[LLM may struggle with different schemas per run]** → The same LLM sees different `finish` schemas depending on level. Mitigation: the schema is small and well-described; the prompt addendum reinforces expectations. This is structurally similar to how function calling works — the model reads the schema.

- **[Global tool registration under same name]** → If two levels are accidentally registered in the same process, one clobbers the other. Mitigation: each summarization run creates a fresh agent with exactly one finish tool. The `build_summarizer_tools()` function takes a `level` parameter and registers only the matching tool.

- **[models.py shim maintenance]** → Two import paths for the same types. Mitigation: the shim is tiny (re-exports only) and tests verify backward compatibility.
