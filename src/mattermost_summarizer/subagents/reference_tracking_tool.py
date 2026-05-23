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
    is_followed: bool | None = None
    can_follow_deeper: bool | None = None
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

        if cmd == "classify_text":
            if not action.url:
                return ReferenceTrackingObservation(
                    command=cmd, error="Text content required for classify_text command"
                )
            from mattermost_summarizer.tools.reference_tracker import classify_urls_in_text

            classified_list = classify_urls_in_text(action.url, self._tracker)
            return ReferenceTrackingObservation(
                command=cmd,
                classified_urls=[
                    {
                        "url": c.url,
                        "reference_type": c.reference_type.value,
                        "agent_type": c.agent_type,
                    }
                    for c in classified_list
                ],
                result=f"Found {len(classified_list)} URLs",
            )

        if cmd == "mark_followed":
            if not action.url:
                return ReferenceTrackingObservation(command=cmd, error="URL required for mark_followed command")
            # Hold the lock across the check-then-act to prevent TOCTOU races
            # when tools run concurrently.
            with self._tracker.lock():
                if not self._tracker.can_follow_deeper():
                    return ReferenceTrackingObservation(
                        command=cmd,
                        url=action.url,
                        error=f"Cannot follow URL: maximum depth ({self._tracker.max_depth}) reached. "
                        f"Current depth: {self._tracker.current_depth}",
                    )
                self._tracker.mark_followed(action.url)
            return ReferenceTrackingObservation(command=cmd, url=action.url, result="URL marked as followed")

        if cmd == "is_followed":
            if not action.url:
                return ReferenceTrackingObservation(command=cmd, error="URL required for is_followed command")
            is_followed = self._tracker.has_been_followed(action.url)
            return ReferenceTrackingObservation(
                command=cmd,
                url=action.url,
                is_followed=is_followed,
                result="URL has been followed" if is_followed else "URL not yet followed",
            )

        if cmd == "can_follow":
            can_follow = self._tracker.can_follow_deeper()
            depth_msg = "can follow more" if can_follow else "max depth reached"
            return ReferenceTrackingObservation(
                command=cmd,
                can_follow_deeper=can_follow,
                current_depth=self._tracker.current_depth,
                max_depth=self._tracker.max_depth,
                result=f"Depth {self._tracker.current_depth}/{self._tracker.max_depth} - {depth_msg}",
            )

        if cmd == "increment_depth":
            self._tracker.increment_depth()
            return ReferenceTrackingObservation(
                command=cmd,
                current_depth=self._tracker.current_depth,
                max_depth=self._tracker.max_depth,
                result=f"Depth incremented to {self._tracker.current_depth}",
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
                    "classify - Classify a single URL (param: url) -> returns reference type and agent type; "
                    "classify_text - Extract and classify all URLs from text content (param: url as text) "
                    "-> returns list of classified URLs; "
                    "mark_followed - Mark a URL as followed to prevent cycles (param: url); "
                    "is_followed - Check if a URL has already been followed (param: url); "
                    "can_follow - Check if we can follow another level of references; "
                    "increment_depth - Increment the depth counter after following a reference; "
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
