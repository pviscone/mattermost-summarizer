## Why

When the CLI output is read by a human in a terminal, the current plain-text formatting
(rows of `=` separators) is functional but visually flat — all sections compete equally
for attention. Using `rich` for TTY-detected output makes the summary significantly easier
to scan and read, at zero cost when output is piped.

## What Changes

- Add `rich` as an explicit direct dependency (currently only transitive via `openhands-sdk`)
- Add a `render_rich(console)` method to `SummaryResult` that formats output using rich
  typography (bold headers, colored bullets, dim metadata) — Option 3 "Minimal" style
- Update `summarize.py` to detect TTY at runtime: use `rich` rendering when stdout is a
  TTY, fall back to `str(result)` (current plain text) when piped or redirected
- `__str__` on `SummaryResult` is unchanged — pipe-safe plain text forever

## Capabilities

### New Capabilities

- `rich-output`: TTY-aware rich formatting of `SummaryResult` for terminal display.
  Detects `sys.stdout.isatty()`, renders with bold/colored typography when true,
  falls back to plain text otherwise. No boxes or panels — typography only.

### Modified Capabilities

<!-- none — __str__ and JSON output paths are unchanged -->

## Impact

- `summarize.py`: add TTY detection + rich render path
- `src/mattermost_summarizer/models.py`: add `render_rich(console: Console) -> None` method
- `pyproject.toml`: add `rich` as explicit dependency
- No API surface changes — library users (`MattermostSummarizer`) are unaffected
- No changes to `--output json` path
