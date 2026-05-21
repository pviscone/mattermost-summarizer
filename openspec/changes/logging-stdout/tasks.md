## 1. Setup Logging Configuration

- [ ] 1.1 In `src/mattermost_summarizer/utils.py` (or a new `logging.py`), add a function `setup_logging(log_file: str = "mattermost-summarizer.log")` to configure the Python root logger and OpenHands loggers to write exclusively to a `FileHandler`.
- [ ] 1.2 Remove any default `StreamHandler(sys.stdout)` or `StreamHandler(sys.stderr)` from the root logger and `openhands` loggers within `setup_logging`.

## 2. Integrate Logging in Application

- [ ] 2.1 Update `summarize.py` CLI script to call `setup_logging()` at the very beginning of the `main()` function.
- [ ] 2.2 Wrap the `summarizer.summarize()` call in `summarize.py` or within `summarizer.py` with `contextlib.redirect_stdout(sys.stderr)` (or redirect to a dummy file/null) if any underlying library uses hardcoded `print()` statements, ensuring `stdout` remains pristine.

## 3. Testing and Verification

- [ ] 3.1 Run the `summarize.py` CLI locally and verify that intermediate output (e.g., from the agent) is written to `mattermost-summarizer.log`.
- [ ] 3.2 Verify that piping the CLI output (e.g., `uv run summarize.py <url> > result.txt`) writes only the final `SummaryResult` to `result.txt` without any extra text.
