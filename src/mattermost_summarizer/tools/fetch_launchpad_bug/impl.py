"""FetchLaunchpadBug tool - retrieves a public Launchpad bug."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from openhands.sdk import Action, Observation, TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition
from pydantic import Field

from mattermost_summarizer.ssrf import check_url_ssrf


class FetchLaunchpadBugAction(Action):
    """Fetch a public Launchpad bug by URL or numeric ID."""

    bug_url_or_id: str = Field(description="Launchpad bug URL or numeric ID")


class FetchLaunchpadBugObservation(Observation):
    """Result of fetching a Launchpad bug."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    importance: str | None = None
    tags: list[str] | None = None
    comments: list[str] | None = None
    total_comments: int | None = None
    error: str | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        if self.error:
            return [TextContent(text=f"Error fetching Launchpad bug: {self.error}")]

        lines: list[str] = []
        lines.append(f"Bug: {self.title}")
        lines.append(f"Status: {self.status} | Importance: {self.importance}")

        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")

        lines.append("")
        if self.description:
            lines.append(f"Description: {self.description}")

        if self.comments:
            lines.append("")
            lines.append(f"Comments ({self.total_comments}):")
            for i, comment in enumerate(self.comments, 1):
                lines.append(f"  {i}. {comment}")

        return [TextContent(text="\n".join(lines))]


class FetchLaunchpadBugExecutor(ToolExecutor[FetchLaunchpadBugAction, FetchLaunchpadBugObservation]):
    """Executor for fetching Launchpad bugs."""

    def __init__(self, client: httpx.Client | None) -> None:
        self.client = client or httpx.Client(timeout=30.0)

    def __call__(
        self, action: FetchLaunchpadBugAction, conversation: object | None = None
    ) -> FetchLaunchpadBugObservation:
        ssrf_result = check_url_ssrf(action.bug_url_or_id)
        if not ssrf_result.is_safe:
            return FetchLaunchpadBugObservation(error=f"URL is not accessible: {ssrf_result.reason}")

        bug_id = self._parse_bug_id(action.bug_url_or_id)
        if bug_id is None:
            return FetchLaunchpadBugObservation(error="Invalid bug URL or ID")

        try:
            bug_data = self._fetch_bug(bug_id)
            if bug_data is None:
                return FetchLaunchpadBugObservation(error="Bug not found or is private")

            comments = self._fetch_comments(bug_data)
            total = bug_data.get("message_count", 0)

            return FetchLaunchpadBugObservation(
                title=bug_data.get("title"),
                description=bug_data.get("description"),
                status=bug_data.get("status"),
                importance=bug_data.get("importance"),
                tags=bug_data.get("tags", []),
                comments=comments,
                total_comments=total,
                error=None,
            )
        except httpx.HTTPError as e:
            return FetchLaunchpadBugObservation(error=f"HTTP error: {e}")
        except Exception as e:
            return FetchLaunchpadBugObservation(error=str(e))

    def _parse_bug_id(self, bug_url_or_id: str) -> str | None:
        import re

        bug_url_or_id = bug_url_or_id.strip()

        url_match = re.search(r"bugs\.launchpad\.net/.+/\+bug/(\d+)", bug_url_or_id)
        if url_match:
            return url_match.group(1)

        if url_match is None:
            url_match = re.search(r"api\.launchpad\.net/1\.0/bugs/(\d+)", bug_url_or_id)
        if url_match:
            return url_match.group(1)

        if re.match(r"^\d+$", bug_url_or_id):
            return bug_url_or_id

        return None

    def _fetch_bug(self, bug_id: str) -> dict[str, Any] | None:
        url = f"https://api.launchpad.net/1.0/bugs/{bug_id}"
        response = self.client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    def _fetch_comments(self, bug_data: dict[str, Any]) -> list[str]:
        messages_link = bug_data.get("messages_collection_link")
        if not messages_link:
            return []

        comments: list[str] = []
        while len(comments) < 50 and messages_link:
            resp = self.client.get(messages_link)
            resp.raise_for_status()
            data = resp.json()

            for entry in data.get("entries", []):
                if len(comments) >= 50:
                    break
                content = entry.get("content", "")
                if content:
                    comments.append(content[:500])

            messages_link = data.get("next_collection_link")
            if not messages_link:
                break

        return comments


class FetchLaunchpadBugTool(ToolDefinition[FetchLaunchpadBugAction, FetchLaunchpadBugObservation]):
    """Tool for fetching a Launchpad bug by URL or ID."""

    @classmethod
    def create(cls, client: httpx.Client | None = None, **kwargs: object) -> Sequence[FetchLaunchpadBugTool]:
        """Create FetchLaunchpadBugTool instance.

        Args:
            client: httpx.Client instance for API calls
            **kwargs: Additional parameters (none supported)

        Returns:
            A sequence containing a single FetchLaunchpadBugTool instance
        """
        return [
            cls(
                description=(
                    "Fetch a public Launchpad bug by URL or numeric ID. "
                    "Returns bug title, description, status, importance, tags, and comments. "
                    "Use this when you encounter a Launchpad bug URL in a thread."
                ),
                action_type=FetchLaunchpadBugAction,
                observation_type=FetchLaunchpadBugObservation,
                executor=FetchLaunchpadBugExecutor(client),
                annotations=ToolAnnotations(
                    title="fetch_launchpad_bug",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


__all__ = [
    "FetchLaunchpadBugAction",
    "FetchLaunchpadBugExecutor",
    "FetchLaunchpadBugObservation",
    "FetchLaunchpadBugTool",
]
