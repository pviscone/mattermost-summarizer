## ADDED Requirements

### Requirement: Fetch public Launchpad bug
The system SHALL provide a `FetchLaunchpadBug` tool that fetches the details of a public Launchpad bug by URL or numeric ID.
- The tool SHALL return: bug title, description, status, importance, tags, and comments (up to 50)
- The tool SHALL accept both a full Launchpad bug URL (e.g., `https://bugs.launchpad.net/ubuntu/+bug/12345`) and a bare numeric ID
- The tool SHALL use the Launchpad REST API v1 (`https://api.launchpad.net/1.0/bugs/{id}`) with no authentication
- Comments exceeding 50 SHALL be truncated; the observation SHALL note how many total comments exist
- The tool SHALL surface a clear error if the bug does not exist or is private

#### Scenario: Fetch a public bug by URL
- **WHEN** the agent calls `FetchLaunchpadBug` with a valid Launchpad bug URL
- **THEN** the observation contains the bug title, description, current status, importance, tags, and up to 50 comments

#### Scenario: Fetch a public bug by numeric ID
- **WHEN** the agent calls `FetchLaunchpadBug` with a bare numeric bug ID (e.g., `12345`)
- **THEN** the observation contains the same fields as fetching by URL

#### Scenario: Bug has more than 50 comments
- **WHEN** the agent calls `FetchLaunchpadBug` for a bug with 120 comments
- **THEN** the observation contains the first 50 comments and notes "Showing 50 of 120 comments"

#### Scenario: Fetch a non-existent or private bug
- **WHEN** the agent calls `FetchLaunchpadBug` with an ID that does not exist or is private
- **THEN** the observation contains an error message indicating the bug could not be retrieved
