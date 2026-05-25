# Project Development Guidelines

This document defines baseline expectations for all development work in this project.

## Base Language

- **Python 3** is the base language for this project
- Use `uv run python` to run Python code (e.g., `uv run --env-file=.env python script.py`)

## Package Management

- **uv** is the package manager for this project
- Use `uv` commands for dependency management:
  - `uv add <package>` - Add dependencies
  - `uv remove <package>` - Remove dependencies
  - `uv sync` - Sync dependencies with lock file
  - `uv lock` - Update lock file
  - `uv run --env-file=.env <command>` - Run commands in project environment

## Code Quality Tools

### Linting

- **ruff** is the linter for this project
- Run with: `uv run ruff check .`
- Configuration should be in `pyproject.toml`

### Type Checking

- **mypy** and **pyright** are used for static type checking
- Run mypy with: `uv run mypy .`
- Run pyright with: `uv run pyright`

## Testing

- **pytest** is the testing framework
- Run tests with: `uv run pytest -n auto`
- Test files should follow `test_*.py` or `*_test.py` naming convention

## Development Workflow

1. Install dependencies: `uv sync`
2. Run linting: `uv run ruff check .`
3. Run type checking: `uv run mypy .` and/or `uv run pyright`
4. Run tests: `uv run pytest -n auto`

## MLflow Tracing

An MLflow server is available at `http://127.0.0.1:5000` for tracing LLM calls.

- **Experiment ID**: `0` — used for mattermost-summarizer runs
- Traces are configured via environment variables in `summarize.py` (OTLP exporter with `http/protobuf` protocol)
- View traces at `http://127.0.0.1:5000` in the browser

## Context Finding

Use the following sources for code and API context:

1. **Installed openhands SDK**: `semble repo=.venv/lib/python3.14/site-packages/openhands`
2. **Full openhands SDK source & examples**: `semble repo=https://github.com/OpenHands/software-agent-sdk.git`
3. **Mattermost source & API docs**: `semble repo=https://github.com/mattermost/mattermost.git`
4. **General documentation**: Use `context7` (resolve library ID then query docs)

### Code Search

Use `semble search` to find code by describing what it does or naming a symbol/identifier, instead of grep:

```bash
semble search "authentication flow" ./my-project
semble search "save_pretrained" ./my-project
semble search "save model to disk" ./my-project --top-k 10
```

Use `semble find-related` to discover code similar to a known location (pass `file_path` and `line` from a prior search result):

```bash
semble find-related src/auth.py 42 ./my-project
```

`path` defaults to the current directory when omitted; git URLs are accepted.

If `semble` is not on `$PATH`, use `uvx --from "semble[mcp]" semble` in its place.

1. Start with `semble search` to find relevant chunks.
2. Inspect full files only when the returned chunk is not enough context.
3. Optionally use `semble find-related` with a promising result's `file_path` and `line` to discover related implementations.
4. Use grep only when you need exhaustive literal matches or quick confirmation of an exact string.

## OpenHands SDK Integration

This project uses the [OpenHands SDK](https://github.com/openhands/software-agent-sdk) for building agents. Key integration patterns:

### Tool Creation Pattern

The OpenHands SDK expects a specific tool creation pattern. **Do NOT** directly instantiate `ToolDefinition` - it is abstract.

```python
# ❌ WRONG - ToolDefinition is abstract, can't be instantiated directly
executor = FetchThreadExecutor(client)
return [ToolDefinition(
    description="...",
    action_type=FetchThreadAction,
    observation_type=FetchThreadObservation,
    executor=executor,
)]

# ✅ CORRECT - Subclass ToolDefinition with create() classmethod
class FetchThreadTool(ToolDefinition[FetchThreadAction, FetchThreadObservation]):
    @classmethod
    def create(cls, client=None, **kwargs):
        executor = FetchThreadExecutor(client) if client else None
        return [cls(
            description="Fetch a Mattermost thread...",
            action_type=FetchThreadAction,
            observation_type=FetchThreadObservation,
            executor=executor,
        )]
```

### Tool Registration and Usage

Two patterns work for providing tools to an `Agent`:

**Pattern A: Register tool globally, reference by name**
```python
from openhands.sdk import Agent, LLM, Tool, register_tool

# Register the tool
register_tool('fetch_thread', FetchThreadTool)

# Use with Agent via Tool spec (only needs name + params)
agent = Agent(
    llm=LLM(model="openai/gpt-4o", api_key=SecretStr("...")),
    tools=[Tool(name='fetch_thread', params={'client': client})]
)
```

**Pattern B: Use tool's kind property directly**
```python
# Agent expects list[openhands.sdk.tool.spec.Tool]
# Tool(name=..., params=...) where name must match ToolDefinition.kind
agent = Agent(llm=llm, tools=[Tool(name='finish', params={})])
```

### Mattermost-Specific Tools

The project includes specialized tools for enriching thread summaries with external context:

- **FetchFile** - Retrieves file attachments from URLs (text files only)
- **FetchLaunchpadBug** - Fetches Launchpad bug details from URLs
- **FetchGitHubIssue** - Fetches GitHub issues/PRs from URLs

These tools are automatically available to the agent when encountering links in Mattermost posts.

### Conversation Types

Two conversation classes exist with different interfaces:

- `Conversation` - Base class, minimal interface
- `LocalConversation` - Subclass with full functionality (`send_message`, `run`, `stuck_detector`)

**Important:** `LocalConversation` is NOT a subclass of `Conversation`. They're parallel branches under `BaseConversation`.

```python
# ❌ WRONG - type checker will complain
def _extract_finish_action(conversation: Conversation, ...):

# ✅ CORRECT - use appropriate type for your needs
def _extract_finish_action(conversation: LocalConversation, ...):
```

### Executor Pattern

`ToolExecutor` is an abstract base class. Implement `__call__`:

```python
from openhands.sdk.tool import ToolExecutor

class FetchThreadExecutor(ToolExecutor[FetchThreadAction, FetchThreadObservation]):
    def __init__(self, client):
        self.client = client

    def __call__(self, action: FetchThreadAction, conversation=None) -> FetchThreadObservation:
        # Implementation
        return FetchThreadObservation(...)

class SummarizerFinishExecutor(ToolExecutor[SummarizerFinishAction, SummarizerFinishObservation]):
    def __call__(self, action: SummarizerFinishAction, conversation=None) -> SummarizerFinishObservation:
        return SummarizerFinishObservation(success=True, summary_provided=True)
```

### Parallel Tool Execution

When executing tools concurrently (e.g. `tool_concurrency_limit > 1` on the `Agent`), the OpenHands SDK `ParallelToolExecutor` restricts concurrency to prevent race conditions. 

By default, the SDK conservatively assumes tools are not thread-safe. If a tool does not explicitly declare resources, the SDK assigns a global mutex on the tool's name (`tool:<name>`), **forcing sequential execution** regardless of the concurrency limit.

To enable true parallel execution for a tool, you must override `declared_resources` on the `ToolDefinition` to return `DeclaredResources` with `declared=True`.

```python
from openhands.sdk.tool.tool import DeclaredResources

class FetchReferenceTool(ToolDefinition[FetchReferenceAction, FetchReferenceObservation]):
    name = "fetch_reference"

    def declared_resources(self, action: FetchReferenceAction) -> DeclaredResources:
        # For thread-safe tools with no shared resource contention
        return DeclaredResources(keys=(), declared=True)
        
        # Alternatively, lock on specific inputs (e.g., prevent duplicate fetches of same URL)
        # return DeclaredResources(keys=(f"url:{action.url}",), declared=True)
```
