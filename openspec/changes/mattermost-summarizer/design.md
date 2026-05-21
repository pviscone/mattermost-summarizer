# Design: Mattermost Conversation Summarizer

## High-level Flow

```
1. User calls MattermostSummarizer.summarize(permalink_url)
2. Summarizer parses URL → extract post_id
3. Summarizer builds MattermostClient, LLM, Tools, Agent, Conversation
4. Conversation.send_message("Summarize thread: {url}")
5. Conversation.run()
6. Agent loop:
   a. LLM reasons about what to do
   b. Calls FetchThread(post_id) → gets thread data
   c. Calls GetUserProfile(user_id) → resolves names (as needed)
   d. May call FetchChannel(channel_id) → gets channel context
   e. Produces structured summary in LLM reasoning
   f. Calls finish(tldr=..., narrative=..., action_items=...) → stops
7. Summarizer scans events for FinishAction
8. Parses into SummaryResult, returns to user
```

## Component Details

### MattermostClient (client.py)

Shared httpx client wrapping Mattermost API v4. All tool executors receive a reference.

```python
class MattermostClient:
    def __init__(self, base_url: str, token: SecretStr):
        self._http = httpx.Client(
            base_url=f"{base_url}/api/v4",
            headers={"Authorization": f"Bearer {token.get_secret_value()}"},
        )

    def get_post_thread(self, post_id: str) -> PostThread: ...
    def get_user(self, user_id: str) -> UserProfile: ...
    def get_channel(self, channel_id: str) -> Channel: ...

    def close(self): ...
```

Design decisions:
- Sync client (OpenHands tools execute synchronously)
- Lazy — no calls until a tool invokes a method
- Shared instance across all tool executors for connection pooling

### Permalink Parsing

Mattermost permalinks follow: `https://{server}/{team}/pl/{post_id}`

```python
def parse_permalink(url: str) -> str:
    """Extract post_id from Mattermost permalink."""
    # /canonical/pl/injbzc9x1igkmk6icenahhj7ho
    #                ^^  ^^^^^^^^^^^^^^^^^^^^^^^^
    #               /pl/        post_id
    match = re.search(r"/pl/([a-z0-9]+)", url)
    if not match:
        raise ValueError(f"Not a valid Mattermost permalink: {url}")
    return match.group(1)
```

### Tool: FetchThread

**Action:**
```python
class FetchThreadAction(Action):
    post_id: str = Field(description="Root post ID to fetch thread for")
```

**Observation:**
```python
class FetchThreadObservation(Observation):
    root_post: PostData       # root post content, author, timestamp
    replies: list[PostData]   # ordered replies
    channel_id: str
    total_replies: int

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        # Format thread as readable conversation for LLM
        ...
```

**Executor:**
```python
class FetchThreadExecutor(ToolExecutor[FetchThreadAction, FetchThreadObservation]):
    def __init__(self, client: MattermostClient):
        self.client = client

    def __call__(self, action: FetchThreadAction, conversation=None) -> FetchThreadObservation:
        raw = self.client.get_post_thread(action.post_id)
        # Parse API response → structured PostData
        # Sort replies by create_at timestamp
        # Return observation with formatted to_llm_content
```

**to_llm_content format** — this is what the agent "sees":

```
Thread in channel: #channel-name
Root post by @username at 2026-05-21 09:00:
  Message text here...

--- Replies (3) ---

1. @alice at 09:05:
   Reply text...

2. @bob at 09:12:
   Another reply...

3. @alice at 09:15:
   Follow-up...
```

Key design: user IDs are **not** resolved in FetchThread — that's GetUserProfile's job. But we include user IDs so the agent can call GetUserProfile when needed. Alternatively, FetchThread could auto-resolve (trade-off below).

**Trade-off: Auto-resolve vs explicit resolve**

| Approach | Pros | Cons |
|----------|------|------|
| Auto-resolve in FetchThread | Simpler for agent, one tool call | N+1 API calls, slower, wasteful if agent doesn't need all names |
| Explicit (agent calls GetUserProfile) | Agent controls what it resolves | More tool calls, agent might forget to resolve |

**Recommendation:** Auto-resolve in FetchThread for v1. The agent's job is summarization, not API orchestration. GetUserProfile stays available for cases where the agent needs details about a user mentioned in passing.

### Tool: GetUserProfile

**Action:**
```python
class GetUserAction(Action):
    user_id: str = Field(description="User ID to look up")
```

**Observation:**
```python
class GetUserObservation(Observation):
    username: str
    display_name: str
    email: str | None
    nickname: str | None

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text=f"@{self.username} ({self.display_name})")]
```

### Tool: FetchChannel

**Action:**
```python
class FetchChannelAction(Action):
    channel_id: str = Field(description="Channel ID to look up")
```

**Observation:**
```python
class FetchChannelObservation(Observation):
    name: str
    display_name: str
    purpose: str | None
    header: str | None
    team_name: str | None

    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        ...
```

### Tool: finish

**Action:**
```python
class FinishAction(Action):
    tldr: str = Field(description="Bullet-point TL;DR of the conversation")
    narrative: str = Field(description="Chronological narrative of the conversation")
    action_items: list[str] = Field(default_factory=list, description="Decisions, todos, or follow-ups mentioned")
    participants: list[str] = Field(default_factory=list, description="People who contributed to the thread")
```

**Observation:**
```python
class FinishObservation(Observation):
    @property
    def to_llm_content(self) -> Sequence[TextContent | ImageContent]:
        return [TextContent(text="Summary complete.")]
```

**Executor:** Trivial — just returns the observation. The real work is extracting the FinishAction from the conversation events in `summarizer.py`.

### Agent System Prompt

The agent needs a carefully crafted system prompt:

```
You are a Mattermost conversation summarizer. Your job is to read conversation threads and produce structured summaries.

When given a Mattermost permalink:
1. Fetch the thread to get all posts
2. Fetch channel context if the thread is unclear without it
3. Resolve any unclear user references
4. Produce a summary with:
   - TL;DR: 3-5 bullet points capturing the key outcomes
   - Narrative: Chronological walkthrough of the conversation, noting who said what and how the discussion evolved
   - Action items: Any decisions, follow-ups, or assignments mentioned
   - Participants: List of people who contributed
5. Call the finish tool with your summary

Be concise but thorough. Focus on substance, not procedural messages ("thanks!", "agreed", etc.).
```

### Summarizer (summarizer.py)

```python
class MattermostSummarizer:
    @classmethod
    def from_config(cls, path: Path) -> "MattermostSummarizer": ...
    
    @classmethod
    def from_env(cls) -> "MattermostSummarizer": ...

    def summarize(self, permalink_url: str) -> SummaryResult:
        post_id = parse_permalink(permalink_url)
        
        client = MattermostClient(self.config.mattermost_url, self.config.mattermost_token)
        
        llm = LLM(
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_base_url,
        )
        
        tools = build_mattermost_tools(client)  # registers FetchThread, GetUser, FetchChannel, finish
        
        agent = Agent(llm=llm, tools=tools)
        
        conversation = Conversation(agent=agent, workspace=".")
        conversation.send_message(
            f"Summarize this Mattermost thread: {permalink_url}\n"
            f"The post ID is: {post_id}"
        )
        conversation.run()
        
        # Scan events for FinishAction
        finish_event = extract_finish_action(conversation)
        
        return SummaryResult(
            tldr=finish_event.tldr,
            narrative=finish_event.narrative,
            action_items=finish_event.action_items,
            participants=finish_event.participants,
            metadata=SummaryMeta(
                thread_length=...,
                cost=llm.metrics.accumulated_cost,
                model_used=self.config.llm_model,
                duration_seconds=...,
            ),
        )
```

### Config (config.py)

```python
class MattermostSummarizerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MM_",
        toml_file="mattermost-summarizer.toml",
    )
    
    mattermost_url: HttpUrl
    mattermost_token: SecretStr
    llm_model: str = "openai/gpt-4o"
    llm_api_key: SecretStr
    llm_base_url: str | None = None
```

TOML is primary. Env vars override with `MM_` prefix. Order of precedence: env var > TOML file > defaults.

### SummaryResult

```python
class SummaryMeta(BaseModel):
    thread_length: int
    cost: float
    model_used: str
    duration_seconds: float

class SummaryResult(BaseModel):
    tldr: str
    narrative: str
    action_items: list[str]
    participants: list[str]
    metadata: SummaryMeta
    
    def __str__(self) -> str:
        # Pretty formatted output
        ...
```

## Error Handling

| Scenario | Handling |
|----------|----------|
| Invalid permalink | ValueError before agent starts |
| Auth failure (401) | MattermostClient raises, caught in summarizer, clear error message |
| Post not found (404) | FetchThread returns observation with error, agent decides what to do |
| Thread too large for context | Agent uses context condenser (built into OpenHands) or fetches in chunks (v2) |
| Agent gets stuck | StuckDetector halts, summarizer returns partial result or raises |
| LLM rate limit | OpenHands LLM class handles retries automatically |
| Network timeout | httpx timeout config, caught in MattermostClient |

## Long Thread Strategy

For threads exceeding the LLM context window (~100+ replies):

**v1:** Let OpenHands' built-in context condenser handle it. The condenser compresses earlier conversation history when the context gets large. This is "good enough" for most cases.

**v2 (if condenser isn't sufficient):**
- Add a `FetchThreadPage` tool that paginates through thread replies
- Agent reads chunks, builds mental model, summarizes incrementally
- More expensive (more LLM calls) but handles arbitrarily long threads

## Data Models

```python
class PostData(BaseModel):
    id: str
    author_id: str
    author_username: str | None  # resolved if auto-resolve is on
    author_display_name: str | None
    message: str
    created_at: datetime
    reply_count: int = 0
    reactions: list[ReactionData] = []
    attachments: list[str] = []  # file IDs
    props: dict = {}

class PostThread(BaseModel):
    root: PostData
    replies: list[PostData]
    channel_id: str
    channel_name: str | None
    total_replies: int
```
