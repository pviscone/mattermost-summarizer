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

### Using GitHub Copilot

If you have a GitHub Copilot subscription, you can use it instead of a separate LLM provider. LiteLLM has native support via the `github_copilot/` provider prefix:

```toml
[mattermost]
url = "https://chat.canonical.com"
token = "your-mattermost-token"

[llm]
model   = "github_copilot/gpt-5-mini"
api_key = "ghp_your_github_personal_access_token"
```

Your GitHub PAT needs the `copilot` scope. No `base_url` is required — LiteLLM routes automatically.
**Note**: Only gpt models are supported at this time.

See [docs/gh-copilot.md](docs/gh-copilot.md) for more details.

### Environment Variables

You can use environment variables with `MM_` prefix instead of a config file:

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
