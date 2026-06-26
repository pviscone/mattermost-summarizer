"""FetchChannel tool - retrieves a Mattermost channel."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

import httpx
from openhands.sdk import Action, Observation, TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition
from pydantic import Field

if TYPE_CHECKING:
    from mattermost_summarizer.client import MattermostClient

from mattermost_summarizer.exceptions import AuthenticationError, ChannelNotFoundError
from mattermost_summarizer.sanitization import format_with_delimiter, sanitize_text

logger = logging.getLogger(__name__)


class FetchChannelAction(Action):
    """Fetch a Mattermost channel by ID or name."""

    channel_id: str | None = Field(default=None, description="Channel ID to look up")
    channel_name: str | None = Field(default=None, description="Channel name to look up (use with team_name)")
    team_name: str | None = Field(default=None, description="Team name (required when using channel_name)")


class FetchChannelObservation(Observation):
    """Result of fetching a channel."""

    channel_id: str
    name: str
    display_name: str
    purpose: str | None = None
    header: str | None = None
    team_name: str | None = None
    error: str | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        if self.error:
            return [TextContent(text=f"Error fetching channel: {self.error}")]

        lines = [f"Channel: #{self.display_name}"]

        if self.team_name:
            lines.append(f"Team: {self.team_name}")

        if self.purpose:
            lines.append(f"Purpose: {sanitize_text(self.purpose)}")

        if self.header:
            lines.append(f"Header: {sanitize_text(self.header)}")

        return [TextContent(text=format_with_delimiter("\n".join(lines)))]


class FetchChannelExecutor(ToolExecutor[FetchChannelAction, FetchChannelObservation]):
    """Executor for fetching Mattermost channels."""

    def __init__(self, client: MattermostClient | None) -> None:
        self.client = client

    def _get_channel_id_by_name(self, team_name: str, channel_name: str) -> str | None:
        """Look up channel ID by team name and channel name.

        Args:
            team_name: The team name
            channel_name: The channel name

        Returns:
            Channel ID if found, None otherwise
        """
        if self.client is None:
            return None
        try:
            channel = self.client.get_channel_by_name(team_name, channel_name)
            return channel.id
        except Exception:
            pass
        return None

    def __call__(self, action: FetchChannelAction, conversation: object | None = None) -> FetchChannelObservation:
        if self.client is None:
            return FetchChannelObservation(
                channel_id=action.channel_id or "",
                name="",
                display_name="",
                purpose=None,
                header=None,
                team_name=None,
                error="Client not provided",
            )

        channel_id = action.channel_id
        if not channel_id and action.channel_name and action.team_name:
            channel_id = self._get_channel_id_by_name(action.team_name, action.channel_name)
            if not channel_id:
                return FetchChannelObservation(
                    channel_id="",
                    name="",
                    display_name="",
                    purpose=None,
                    header=None,
                    team_name=None,
                    error=f"Channel not found: {action.channel_name} in team {action.team_name}",
                )
        elif not channel_id:
            return FetchChannelObservation(
                channel_id="",
                name="",
                display_name="",
                purpose=None,
                header=None,
                team_name=None,
                error="Either channel_id or channel_name+team_name must be provided",
            )

        try:
            channel = self.client.get_channel(channel_id)
            return FetchChannelObservation(
                channel_id=channel.id,
                name=channel.name,
                display_name=channel.display_name,
                purpose=channel.purpose,
                header=channel.header,
                team_name=channel.team_name,
                error=None,
            )
        except ChannelNotFoundError:
            return FetchChannelObservation(
                channel_id=channel_id,
                name="",
                display_name="",
                purpose=None,
                header=None,
                team_name=None,
                error="Resource not found or access denied.",
            )
        except (AuthenticationError, httpx.HTTPError) as e:
            logger.warning("Error fetching channel: %s", e)
            return FetchChannelObservation(
                channel_id=channel_id,
                name="",
                display_name="",
                purpose=None,
                header=None,
                team_name=None,
                error="Failed to fetch channel.",
            )


class FetchChannelTool(ToolDefinition[FetchChannelAction, FetchChannelObservation]):
    """Tool for fetching a Mattermost channel by ID."""

    @classmethod
    def create(cls, client: MattermostClient | None = None, **kwargs: object) -> Sequence[FetchChannelTool]:
        """Create FetchChannelTool instance.

        Args:
            client: MattermostClient instance for API calls
            **kwargs: Additional parameters (none supported)

        Returns:
            A sequence containing a single FetchChannelTool instance
        """
        return [
            cls(
                description=(
                    "Fetch a Mattermost channel to get context about where a thread is located. "
                    "Returns channel name, purpose, and team information. "
                    "Provide channel_id directly, OR channel_name with team_name to look up the ID first."
                ),
                action_type=FetchChannelAction,
                observation_type=FetchChannelObservation,
                executor=FetchChannelExecutor(client),
                annotations=ToolAnnotations(
                    title="fetch_channel",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


__all__ = [
    "FetchChannelAction",
    "FetchChannelExecutor",
    "FetchChannelObservation",
    "FetchChannelTool",
]
