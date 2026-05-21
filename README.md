# Mattermost Summarizer

An agentic tool that summarizes Mattermost conversation threads using the OpenHands SDK.

## Installation

```bash
uv add mattermost-summarizer
```

## Configuration

Create a `mattermost-summarizer.toml` config file:

```toml
[mattermost]
url = "https://chat.canonical.com"
token = "your-mattermost-token"

[llm]
model = "openai/gpt-4o"
api_key = "your-llm-api-key"
base_url = "https://api.openai.com/v1"  # optional
```

Or use environment variables with `MM_` prefix:

```bash
export MM_MATTERMOST_URL=https://chat.canonical.com
export MM_MATTERMOST_TOKEN=your-token
export MM_LLM_API_KEY=your-key
```

## Usage

```python
from mattermost_summarizer import MattermostSummarizer

summarizer = MattermostSummarizer.from_config("mattermost-summarizer.toml")
result = summarizer.summarize("https://chat.canonical.com/canonical/pl/abc123xyz")

print(result)  # Pretty formatted output
print(result.tldr)  # Just the TL;DR
```

## License

GPLv3
