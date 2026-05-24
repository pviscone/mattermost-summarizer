"""Reference tracking tool for orchestrator."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from openhands.sdk import Action, Observation
from openhands.sdk.llm.message import TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import ToolDefinition

if TYPE_CHECKING:
    from mattermost_summarizer.tools.reference_tracker import ReferenceTracker


class ReferenceTrackingAction(Action):
    """Action for reference tracking operations."""

    command: str
    url: str | None = None


class ReferenceTrackingObservation(Observation):
    """Observation from reference tracking operations."""

    command: str
    url: str | None = None
    result: str | None = None
    outcome: str | None = None
    current_depth: int | None = None
    max_depth: int | None = None
    classified_urls: list[dict[str, Any]] | None = None
    error: str | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        from openhands.sdk.llm.message import TextContent

        if self.error:
            return [TextContent(text=f"Error: {self.error}")]
        if self.result:
            parts = [self.result]
            if self.classified_urls:
                parts.append("Classified URLs:")
                for u in self.classified_urls:
                    parts.append(f"  - {u['url']} ({u['reference_type']} -> {u['agent_type']})")
            return [TextContent(text="\n".join(parts))]
        if self.classified_urls:
            lines = ["Found URLs:"]
            for u in self.classified_urls:
                lines.append(f"  - {u['url']} ({u['reference_type']}) -> {u['agent_type']}")
            return [TextContent(text="\n".join(lines))]
        return [TextContent(text=f"Command: {self.command}")]


class ReferenceTrackingExecutor(ToolExecutor[ReferenceTrackingAction, ReferenceTrackingObservation]):
    """Executor for reference tracking operations."""

    def __init__(self, tracker: ReferenceTracker | None = None) -> None:
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        self._tracker = tracker or ReferenceTracker()

    def __call__(
        self, action: ReferenceTrackingAction, conversation: object | None = None
    ) -> ReferenceTrackingObservation:
        cmd = action.command

        if cmd == "follow_url":
            if not action.url:
                return ReferenceTrackingObservation(command=cmd, error="URL required for follow_url command")
            with self._tracker.lock():
                if self._tracker.has_been_followed(action.url):
                    return ReferenceTrackingObservation(
                        command=cmd,
                        url=action.url,
                        outcome="already_followed",
                        result="URL has already been followed",
                    )
                # Per-URL depth: look up registered depth (root URLs have None → always allowed)
                url_depth = self._tracker.get_depth_for(action.url)
                if url_depth is not None and url_depth >= self._tracker.max_depth:
                    return ReferenceTrackingObservation(
                        command=cmd,
                        url=action.url,
                        outcome="depth_exceeded",
                        current_depth=url_depth,
                        max_depth=self._tracker.max_depth,
                        result=f"Maximum depth ({self._tracker.max_depth}) reached",
                    )
                # When max_depth=0, only the root URL may be fetched; reject unregistered URLs afterward
                if url_depth is None and self._tracker.max_depth == 0 and len(self._tracker.followed_urls) > 0:
                    return ReferenceTrackingObservation(
                        command=cmd,
                        url=action.url,
                        outcome="depth_exceeded",
                        current_depth=0,
                        max_depth=self._tracker.max_depth,
                        result="No reference following allowed at this summary level (max_depth=0).",
                    )
                effective_depth = url_depth if url_depth is not None else 0
                self._tracker.mark_followed(action.url, effective_depth)
            return ReferenceTrackingObservation(
                command=cmd,
                url=action.url,
                outcome="success",
                current_depth=effective_depth,
                max_depth=self._tracker.max_depth,
                result="URL marked as followed",
            )

        if cmd == "classify":
            if not action.url:
                return ReferenceTrackingObservation(command=cmd, error="URL required for classify command")
            from mattermost_summarizer.tools.reference_tracker import classify_url_full

            classified = classify_url_full(action.url)
            return ReferenceTrackingObservation(
                command=cmd,
                url=action.url,
                result=f"{classified.reference_type.value} -> {classified.agent_type}",
                classified_urls=[
                    {
                        "url": classified.url,
                        "reference_type": classified.reference_type.value,
                        "agent_type": classified.agent_type,
                    }
                ],
            )

        if cmd == "reset":
            self._tracker.reset()
            return ReferenceTrackingObservation(
                command=cmd,
                current_depth=0,
                max_depth=self._tracker.max_depth,
                result="Tracker reset",
            )

        return ReferenceTrackingObservation(command=cmd, error=f"Unknown command: {cmd}")


class ReferenceTrackingTool(ToolDefinition[ReferenceTrackingAction, ReferenceTrackingObservation]):
    """Tool for tracking followed references to prevent cycles and manage depth."""

    name = "track_references"

    @classmethod
    def create(cls, tracker: ReferenceTracker | None = None, **kwargs: object) -> Sequence[ReferenceTrackingTool]:
        return [
            cls(
                description=(
                    "Track and classify URLs to prevent cycles during recursive reference following. "
                    "Commands: "
                    "follow_url - Atomically check, mark, and register a URL as followed. "
                    "Returns: success | already_followed | depth_exceeded (param: url); "
                    "classify - Classify a single URL to get its type and target sub-agent (param: url); "
                    "reset - Reset tracker state for a new summary operation"
                ),
                action_type=ReferenceTrackingAction,
                observation_type=ReferenceTrackingObservation,
                executor=ReferenceTrackingExecutor(tracker),
            )
        ]


__all__ = [
    "ReferenceTrackingTool",
    "ReferenceTrackingAction",
    "ReferenceTrackingObservation",
    "ReferenceTrackingExecutor",
]
