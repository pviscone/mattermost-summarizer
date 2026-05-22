# Github Copilot

## Creating a Token for Copilot

[GitHub](https://github.com/orgs/community/discussions/183370) recommends using fine-grained personal access tokens for better security. \[[1](https://docs.github.com/en/enterprise-server@3.20/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)\]

1. Navigate to Settings: Click your profile picture \> Settings \> Developer settings \> Personal access tokens \> Fine-grained tokens.
2. Generate New Token: Click Generate new token.
3. Set Permissions:
   * Repository Access: Select the repositories Copilot needs to read (e.g., private work repos).
   * Permissions: Under "Account permissions" or "Repository permissions," find and select Copilot Requests (set to Read).
4. Save and Copy: Click Generate token and copy it immediately; it won't be shown again.

## Configure the tool
```
# mattermost-summarizer.toml
[llm]
model    = "github/gpt-5-mini"
api_key  = "ghp_your_github_token"
```

## Supported models
As of 2026-05-22, only gpt-* models are supported due to a [liteLLM + Claude bug](https://github.com/BerriAI/litellm/issues/24565)
