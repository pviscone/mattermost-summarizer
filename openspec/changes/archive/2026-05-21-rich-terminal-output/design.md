## Context

`SummaryResult.__str__()` produces pipe-safe plain text with `=` separators. This is
the right default for scripting. But when a human runs `summarize.py` interactively in
a terminal, all sections look identical — nothing guides the eye to what matters most.

`rich` is already present transitively (via `openhands-sdk`) and is already used in
`visualizer.py`. The CLI entry point in `summarize.py` calls `print(str(result))` with
no TTY awareness.

## Goals / Non-Goals

**Goals:**
- Render `SummaryResult` with rich typography (bold, color, dim) when stdout is a TTY
- Fall back silently to `str(result)` when stdout is piped or redirected
- Add `rich` as an explicit direct dependency (not rely on transitive)
- Keep `__str__` and `--output json` paths entirely unchanged

**Non-Goals:**
- Panels, boxes, or tables (Option 1 / Option 2 style — agreed out of scope)
- Rich formatting for error messages in `summarize.py`
- Any change to the public `MattermostSummarizer` API
- Theming or color configuration

## Decisions

### D1: Typography-only style ("Option 3 Minimal")

Bold colored section headers, colored bullets, dim metadata line. No `Panel`, no `Table`,
no `Rule` borders. Rationale: degrades gracefully on narrow terminals; no visual noise;
closest to how well-regarded CLI tools (`bat`, `delta`, `gh`) present structured text.

Alternatives considered:
- **Option 1 (Panels)**: Rejected — heavy, `Panel` adds fixed chrome that competes with
  content width.
- **Option 2 (Table for actions)**: Rejected now — requires structured owner data the LLM
  doesn't currently return. Good future change.

### D2: `render_rich(console: Console) -> None` method on `SummaryResult`

A dedicated method keeps rich entirely out of `__str__`. Library consumers who never touch
the CLI are unaffected. The method accepts a `Console` so callers control where output
goes and tests can inject a `Console(file=StringIO())`.

Alternatives considered:
- **Monkey-patching `__str__`**: Would break pipe-safety and library usage.
- **Standalone function in `summarize.py`**: Harder to test, couples renderer to CLI.

### D3: TTY detection in `summarize.py` via `sys.stdout.isatty()`

Single call at the output site. If true: create `Console()` (defaults to stdout) and call
`result.render_rich(console)`. If false: `print(str(result))` as today.

`rich.Console` also has its own `is_terminal` / `force_terminal` flags but using
`sys.stdout.isatty()` directly is explicit and easily testable.

### D4: `rich` as explicit dependency

`rich` is currently only transitive. Making it explicit documents the intent and protects
against SDK dependency changes silently breaking the terminal output.

## Risks / Trade-offs

- **`rich` version constraints**: `openhands-sdk` pins its own `rich` version. Adding
  `rich` explicitly with a loose lower bound (`>=10.0`) should resolve without conflict.
  → Mitigation: run `uv lock` after adding and check for conflicts.

- **`isatty()` on unusual stdout**: Some terminal multiplexers (tmux pipes, CI log
  capturers) may return `True` for `isatty()` but not actually render ANSI well.
  → Acceptable — `rich` handles this gracefully; worst case is ANSI escapes in a log.

- **Test coverage**: `render_rich` needs a `Console(file=StringIO(), force_terminal=True)`
  fixture to exercise the rich path without a real TTY.
  → Mitigation: covered in tasks.

## Migration Plan

No migration needed — additive change, existing behaviour preserved on all non-TTY paths.
Rollback: revert the three file changes (summarize.py, models.py, pyproject.toml).

## Open Questions

- None. Design is fully resolved.
