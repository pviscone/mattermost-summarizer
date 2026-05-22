## ADDED Requirements

### Requirement: TTY-aware rich output
The CLI SHALL detect whether stdout is a TTY at runtime and render `SummaryResult`
with rich typography (bold section headers, colored bullets, dim metadata) when it is.
When stdout is not a TTY (pipe, redirect, file), the CLI SHALL fall back to plain-text
output identical to the current `str(result)` behaviour.

#### Scenario: Rich output on interactive terminal
- **WHEN** `summarize.py` runs and `sys.stdout.isatty()` returns `True`
- **THEN** the summary is rendered via `SummaryResult.render_rich(console)` with ANSI styling

#### Scenario: Plain fallback when piped
- **WHEN** `summarize.py` runs and stdout is piped (e.g. `summarize.py url | grep ...`)
- **THEN** the summary is rendered via `str(result)` with no ANSI escape codes

#### Scenario: Plain fallback when redirected to file
- **WHEN** `summarize.py` runs with stdout redirected (e.g. `summarize.py url > out.txt`)
- **THEN** the summary is rendered via `str(result)` with no ANSI escape codes

#### Scenario: JSON output unaffected
- **WHEN** `--output json` flag is passed
- **THEN** output is always `model_dump_json` regardless of TTY state

### Requirement: Rich render method on SummaryResult
`SummaryResult` SHALL expose a `render_rich(console: Console) -> None` method that
writes the full summary to the given `Console` using typography-only rich formatting
(no Panel, no Table, no Rule decorations). The method SHALL NOT alter `__str__`.

#### Scenario: Section headers are bold and colored
- **WHEN** `render_rich` is called
- **THEN** section titles (TL;DR, KEY FINDINGS, NARRATIVE, ACTION ITEMS, PARTICIPANTS) are rendered bold

#### Scenario: Bullets are visually distinct
- **WHEN** key_findings, action_items are non-empty
- **THEN** each item is prefixed with a colored bullet character

#### Scenario: Metadata line is de-emphasised
- **WHEN** `render_rich` is called
- **THEN** the metadata line (model, tokens, cost, duration) is rendered dim/muted

#### Scenario: Empty optional sections are omitted
- **WHEN** `key_findings`, `action_items`, or `participants` are empty lists
- **THEN** those sections are not rendered (same as `__str__` behaviour)

#### Scenario: Console injection for testing
- **WHEN** a `Console(file=StringIO(), force_terminal=True)` is passed to `render_rich`
- **THEN** the method writes to that console without accessing `sys.stdout` directly

### Requirement: rich as explicit dependency
The project's `pyproject.toml` SHALL declare `rich` as a direct dependency with a
minimum version bound, independent of any transitive dependency from `openhands-sdk`.

#### Scenario: rich resolvable after explicit addition
- **WHEN** `uv add rich` is run
- **THEN** `uv lock` resolves without conflicts and `rich` appears in `[project.dependencies]`
