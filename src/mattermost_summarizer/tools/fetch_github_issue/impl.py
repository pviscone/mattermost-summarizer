"""FetchGitHubIssue tool - retrieves a GitHub issue or pull request."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import httpx
from openhands.sdk import Action, Observation, TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition
from pydantic import Field, SecretStr

from mattermost_summarizer.ssrf import check_url_ssrf


class FetchGitHubIssueAction(Action):
    """Fetch a GitHub issue or pull request by URL."""

    url: str = Field(description="GitHub issue or PR URL (e.g., https://github.com/owner/repo/issues/123)")


class FetchGitHubIssueObservation(Observation):
    """Result of fetching a GitHub issue or PR."""

    title: str | None = None
    body: str | None = None
    state: str | None = None
    labels: list[str] | None = None
    assignees: list[str] | None = None
    author: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    comments: list[str] | None = None
    total_comments: int | None = None
    is_pull_request: bool = False
    review_comments: list[str] | None = None
    merge_status: str | None = None
    error: str | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        if self.error:
            return [TextContent(text=f"Error fetching GitHub issue: {self.error}")]

        lines: list[str] = []
        lines.append(f"{'PR' if self.is_pull_request else 'Issue'}: {self.title}")
        lines.append(f"State: {self.state} | Author: {self.author}")

        if self.labels:
            lines.append(f"Labels: {', '.join(self.labels)}")

        if self.assignees:
            lines.append(f"Assignees: {', '.join(self.assignees)}")

        lines.append("")
        if self.body:
            lines.append(f"Description: {self.body}")

        if self.comments:
            lines.append("")
            lines.append(f"Comments ({self.total_comments}):")
            for i, comment in enumerate(self.comments, 1):
                lines.append(f"  {i}. {comment}")

        if self.is_pull_request and self.review_comments:
            lines.append("")
            lines.append(f"Review Comments ({len(self.review_comments)}):")
            for i, comment in enumerate(self.review_comments, 1):
                lines.append(f"  {i}. {comment}")

        if self.merge_status:
            lines.append(f"\nMerge Status: {self.merge_status}")

        return [TextContent(text="\n".join(lines))]


class FetchGitHubIssueExecutor(ToolExecutor[FetchGitHubIssueAction, FetchGitHubIssueObservation]):
    """Executor for fetching GitHub issues and pull requests."""

    def __init__(self, github_token: SecretStr | None = None) -> None:
        self.github_token = github_token
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers: dict[str, str] = {
                "Accept": "application/vnd.github.v3+json",
            }
            if self.github_token:
                headers["Authorization"] = f"Bearer {self.github_token.get_secret_value()}"
            self._client = httpx.Client(
                base_url="https://api.github.com",
                headers=headers,
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> FetchGitHubIssueExecutor:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __call__(
        self, action: FetchGitHubIssueAction, conversation: object | None = None
    ) -> FetchGitHubIssueObservation:
        ssrf_result = check_url_ssrf(action.url)
        if not ssrf_result.is_safe:
            return FetchGitHubIssueObservation(error=f"URL is not accessible: {ssrf_result.reason}")

        parsed = self._parse_url(action.url)
        if parsed is None:
            return FetchGitHubIssueObservation(error="Invalid GitHub issue/PR URL")

        owner, repo, number, is_pr = parsed

        try:
            issue_data = self._fetch_issue(owner, repo, number)
            if issue_data is None:
                return FetchGitHubIssueObservation(error="Issue or PR not found or is private")

            comments = self._fetch_comments(owner, repo, number)
            review_comments: list[str] = []
            merge_status: str | None = None

            if is_pr:
                review_comments = self._fetch_review_comments(owner, repo, number)
                merge_status = issue_data.get("merged", False) and "merged" or issue_data.get("mergeable_state", "")

            labels = [label.get("name", "") for label in issue_data.get("labels", [])]
            assignees = [a.get("login", "") for a in issue_data.get("assignees", [])]

            return FetchGitHubIssueObservation(
                title=issue_data.get("title"),
                body=issue_data.get("body"),
                state=issue_data.get("state"),
                labels=labels,
                assignees=assignees,
                author=issue_data.get("user", {}).get("login"),
                created_at=issue_data.get("created_at"),
                updated_at=issue_data.get("updated_at"),
                comments=comments,
                total_comments=issue_data.get("comments", 0),
                is_pull_request=is_pr,
                review_comments=review_comments if is_pr else None,
                merge_status=merge_status if is_pr else None,
                error=None,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                return FetchGitHubIssueObservation(
                    error="GitHub API rate limit exceeded. Configure github_token in your config to increase limits."
                )
            return FetchGitHubIssueObservation(error=f"HTTP error: {e}")
        except httpx.HTTPError as e:
            return FetchGitHubIssueObservation(error=f"HTTP error: {e}")
        except Exception as e:
            return FetchGitHubIssueObservation(error=str(e))

    def _parse_url(self, url: str) -> tuple[str, str, int, bool] | None:
        url = url.strip()

        pr_pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        issue_pattern = r"github\.com/([^/]+)/([^/]+)/issues/(\d+)"

        pr_match = re.search(pr_pattern, url)
        if pr_match:
            return pr_match.group(1), pr_match.group(2), int(pr_match.group(3)), True

        issue_match = re.search(issue_pattern, url)
        if issue_match:
            return issue_match.group(1), issue_match.group(2), int(issue_match.group(3)), False

        return None

    def _fetch_issue(self, owner: str, repo: str, number: int) -> dict[str, Any] | None:
        url = f"/repos/{owner}/{repo}/issues/{number}"
        response = self.client.get(url)
        if response.status_code == 404:
            return None
        if response.status_code == 403:
            raise httpx.HTTPStatusError("Rate limited", response=response, request=response.request)
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _fetch_comments(self, owner: str, repo: str, number: int) -> list[str]:
        url = f"/repos/{owner}/{repo}/issues/{number}/comments"
        params = {"per_page": 50}
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return [c.get("body", "")[:500] for c in data[:50]]

    def _fetch_review_comments(self, owner: str, repo: str, number: int) -> list[str]:
        url = f"/repos/{owner}/{repo}/pulls/{number}/comments"
        params = {"per_page": 50}
        response = self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return [c.get("body", "")[:500] for c in data[:50]]


class FetchGitHubIssueTool(ToolDefinition[FetchGitHubIssueAction, FetchGitHubIssueObservation]):
    """Tool for fetching a GitHub issue or PR by URL."""

    @classmethod
    def create(cls, github_token: SecretStr | None = None, **kwargs: object) -> Sequence[FetchGitHubIssueTool]:
        """Create FetchGitHubIssueTool instance.

        Args:
            github_token: Optional GitHub token for authenticated requests
            **kwargs: Additional parameters (none supported)

        Returns:
            A sequence containing a single FetchGitHubIssueTool instance
        """
        return [
            cls(
                description=(
                    "Fetch a GitHub issue or pull request by URL. "
                    "Returns title, body, state, labels, assignees, author, dates, and comments. "
                    "For PRs, also returns review comments and merge status. "
                    "Use this when you encounter a GitHub issue or PR URL in a thread."
                ),
                action_type=FetchGitHubIssueAction,
                observation_type=FetchGitHubIssueObservation,
                executor=FetchGitHubIssueExecutor(github_token),
                annotations=ToolAnnotations(
                    title="fetch_github_issue",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


__all__ = [
    "FetchGitHubIssueAction",
    "FetchGitHubIssueExecutor",
    "FetchGitHubIssueObservation",
    "FetchGitHubIssueTool",
]
