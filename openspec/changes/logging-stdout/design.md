## Context

Currently, the `mattermost-summarizer` uses OpenHands SDK to execute a summarization agent. During execution, the agent and the system write logs to `stdout`/`stderr`. This pollutes the console output, making it difficult for users to pipe just the final summary (text or JSON format) to other commands or files. The goal is to enforce a clean `stdout` for the application's core output.

## Goals / Non-Goals

**Goals:**
- Separate diagnostic and progress logging from application results.
- Redirect all OpenHands and system-level logging to a file (e.g., `mattermost-summarizer.log`).
- Keep `stdout` exclusively for the final `SummaryResult` object.

**Non-Goals:**
- We are not changing the format of the `SummaryResult` itself.
- We are not implementing advanced log rotation or log streaming to remote servers; standard file logging is sufficient.

## Decisions

1. **Python Standard Logging Configuration**
   - We will configure Python's root logger and the OpenHands logger to redirect all output to a `FileHandler` pointing to `mattermost-summarizer.log` (or a configured file path) instead of `StreamHandler(sys.stdout)`.
   - The logging configuration will be established at the beginning of the `MattermostSummarizer.summarize()` method or inside `summarize.py` before agent execution starts.
   
2. **OpenHands SDK Logging Override**
   - OpenHands SDK might have its own internal logger instances (e.g., `openhands.core.logger`). We must explicitly target these loggers (or the root logger, if they propagate) and replace their handlers with our `FileHandler`.
   - The CLI `print()` statement that currently outputs the result to `stdout` will remain unchanged.

## Risks / Trade-offs

- **Risk:** Some underlying libraries might hardcode `print()` statements to `stdout`.
  - *Mitigation:* If necessary, use `contextlib.redirect_stdout` to capture stray prints during agent execution, piping them to the log file or `stderr`.
- **Trade-off:** Users lose real-time visibility into what the agent is doing unless they `tail -f` the log file.
  - *Mitigation:* We could potentially output a small "Summarizing..." message to `stderr` that does not interfere with `stdout` pipes, or document that users should tail the log file. We will stick to silence on `stdout` and rely on file logs for debugging.
