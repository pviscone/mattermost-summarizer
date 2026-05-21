## ADDED Requirements

### Requirement: REQ-015 Logging Separation
The system SHALL write all intermediate logs (from standard library logging, OpenHands SDK, or any internal processes) to a file, ensuring that the standard output (`stdout`) is exclusively used for the final output result of the application.

#### Scenario: Running CLI with stdout redirection
- **WHEN** the user runs the `summarize.py` CLI script and pipes the output
- **THEN** the piped `stdout` output contains only the `SummaryResult` string or JSON
- **THEN** a log file (e.g., `mattermost-summarizer.log`) is created or updated with intermediate agent and system logs
