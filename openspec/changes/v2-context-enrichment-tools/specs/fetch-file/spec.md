## ADDED Requirements

### Requirement: Fetch file attachment content
The system SHALL provide a `FetchFile` tool that fetches the content of a Mattermost file attachment by file ID.
- The tool SHALL return the file content as plain text when the file is a text-based format (Content-Type matching `text/*`)
- The tool SHALL return a structured "not readable" observation when the file is binary or an unsupported format
- The "not readable" observation SHALL include: `is_binary: true`, the file's `mime_type`, and a human-readable message
- The tool SHALL use the existing `MattermostClient` for authenticated access to the Mattermost Files API (`GET /api/v4/files/{file_id}`)

#### Scenario: Fetch a plain text file
- **WHEN** the agent calls `FetchFile` with a valid file ID for a `.txt` or `.log` file
- **THEN** the observation contains the file content as a string and `is_binary: false`

#### Scenario: Fetch a binary file
- **WHEN** the agent calls `FetchFile` with a valid file ID for a binary file (e.g., PNG image, PDF)
- **THEN** the observation contains `is_binary: true`, the MIME type, and a message such as "Binary file (image/png): not readable as text"

#### Scenario: Fetch a non-existent file
- **WHEN** the agent calls `FetchFile` with a file ID that does not exist
- **THEN** the observation contains an error message indicating the file was not found
