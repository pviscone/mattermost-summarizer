## ADDED Requirements

### Requirement: Atomic URL follow command
The `track_references` tool SHALL provide a `follow_url` command that atomically checks whether a URL can be followed, marks it as followed, and increments the depth counter in a single call.

- The command SHALL accept a `url` parameter
- The command SHALL return success if the URL was not previously followed AND depth limit has not been reached
- The command SHALL return an `already_followed` result (not an error) if the URL was previously followed
- The command SHALL return a depth-exceeded error if `max_reference_depth` has been reached
- The command SHALL be thread-safe (hold tracker lock for the entire check-mark-increment sequence)
- The `classify_text`, `is_followed`, `can_follow`, `mark_followed`, and `increment_depth` commands SHALL be removed from the tool's public interface

#### Scenario: First follow of a new URL within depth limit
- **WHEN** the orchestrator calls `follow_url` with a URL not previously followed
- **WHEN** current depth is below max_reference_depth
- **THEN** the URL is marked as followed
- **THEN** depth is incremented
- **THEN** the observation result indicates success

#### Scenario: Duplicate URL follow attempt
- **WHEN** the orchestrator calls `follow_url` with a URL already in the followed set
- **THEN** the observation result indicates the URL was already followed
- **THEN** depth is NOT incremented again
- **THEN** no error is returned

#### Scenario: follow_url at max depth
- **WHEN** the orchestrator calls `follow_url` and current depth equals max_reference_depth
- **THEN** the observation result indicates depth limit exceeded
- **THEN** the URL is NOT marked as followed
- **THEN** depth is NOT incremented

### Requirement: Automatic post-delegation URL classification injection
After each delegation completes, the system SHALL automatically inject a message into the orchestrator conversation listing all classified followable URLs found in the delegation result, without requiring the orchestrator to call any classification tool.

- The injection SHALL occur in a post-delegation callback registered at `LocalConversation` construction time
- The callback SHALL call `classify_urls_in_text()` on the delegation observation content
- The callback SHALL format the classified URLs as a user message and send it to the conversation
- The callback SHALL NOT inject a message if no followable URLs are found
- `DelegateTool` SHALL remain unchanged

#### Scenario: Delegation returns content with followable URLs
- **WHEN** a delegation completes and the observation content contains GitHub/Launchpad/Mattermost URLs
- **THEN** a message is automatically appended to the orchestrator conversation
- **THEN** the message lists each classified URL with its type and target sub-agent
- **THEN** the orchestrator can use this list to decide which URLs to follow via `follow_url`

#### Scenario: Delegation returns content with no followable URLs
- **WHEN** a delegation completes and the observation content contains no classified followable URLs
- **THEN** no automatic message is injected
- **THEN** the orchestrator proceeds normally
