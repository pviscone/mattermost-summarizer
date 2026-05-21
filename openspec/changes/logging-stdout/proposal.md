## Why

Currently, when the mattermost-summarizer runs, intermediate outputs from the agent's tool executions are printed to standard output. This makes it difficult to pipe or capture just the final structured summary. The intermediate tool output should be directed to a log file, ensuring that `stdout` is exclusively reserved for the final summary result.

## What Changes

- The agent execution's intermediate logging will be redirected from `stdout`/`stderr` to a dedicated log file.
- The `MattermostSummarizer.summarize()` process will ensure that openhands SDK logger or any other intermediate loggers are configured to output to a file instead of the terminal.
- Only the final structured `SummaryResult` will be printed to `stdout` by the CLI (`summarize.py`).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `mattermost-summarizer`: Requirement changing to enforce strict separation of logging output (to a file) and final application output (to `stdout`).

## Impact

- CLI: Users will have a cleaner `stdout` containing only the final result, making it pipe-friendly.
- Code: The `mattermost_summarizer` package will need to configure logging (e.g. standard library logging, OpenHands SDK logging configuration) appropriately before agent execution.
