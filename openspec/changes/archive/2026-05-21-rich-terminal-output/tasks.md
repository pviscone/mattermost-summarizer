## 1. Dependencies

- [x] 1.1 Add `rich` as an explicit direct dependency: `uv add rich`
- [x] 1.2 Verify `uv lock` resolves without conflicts and `rich` appears in `[project.dependencies]`

## 2. SummaryResult.render_rich

- [x] 2.1 Add `render_rich(self, console: Console) -> None` method to `SummaryResult` in `models.py`
- [x] 2.2 Render TL;DR section: bold header + body text
- [x] 2.3 Render KEY FINDINGS section: bold header + colored bullet per item (skip if empty)
- [x] 2.4 Render NARRATIVE section: bold header + wrapped body text
- [x] 2.5 Render ACTION ITEMS section: bold header + colored bullet per item (skip if empty)
- [x] 2.6 Render PARTICIPANTS section: bold header + joined names (skip if empty)
- [x] 2.7 Render METADATA line: dim/muted — model, thread length, duration, token counts, cost

## 3. CLI TTY detection

- [x] 3.1 In `summarize.py`, replace `print(str(result))` with TTY-aware dispatch:
         if `sys.stdout.isatty()` → create `Console()` and call `result.render_rich(console)`,
         else → `print(str(result))`
- [x] 3.2 Verify `--output json` path is unchanged (no TTY logic applied)

## 4. Tests

- [x] 4.1 Add test for `render_rich` using `Console(file=StringIO(), force_terminal=True)` —
         assert all non-empty sections appear in output
- [x] 4.2 Add test that empty optional sections (key_findings, action_items, participants)
         are omitted from `render_rich` output
- [x] 4.3 Add test that `__str__` is unchanged (plain text, no ANSI codes)

## 5. Verification

- [x] 5.1 Run `uv run ruff check .` — no new lint errors
- [x] 5.2 Run `uv run mypy .` — no new type errors
- [x] 5.3 Run `uv run pytest` — all tests pass
