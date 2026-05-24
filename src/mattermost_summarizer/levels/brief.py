"""Brief summarization level - minimal output with TL;DR and action items only."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from openhands.sdk.tool.tool import ToolAnnotations
from pydantic import Field, field_validator
from rich.console import Console
from rich.text import Text

from mattermost_summarizer.levels.base import (
    SummarizerFinishActionBase,
    SummarizerFinishExecutor,
    SummarizerFinishObservation,
    SummarizerFinishToolBase,
    SummaryResultBase,
)
from mattermost_summarizer.levels.base import (
    inline_bold as _inline_bold,
)

USER_MESSAGE_ADDENDUM = """Level: BRIEF (minimal)

Produce a brief summary with only:
- TL;DR: 2-3 bullet points capturing the key outcomes (as a newline-separated STRING — not a list or array)
- Action items: decisions, todos, follow-ups (as a list of strings, optional)

IMPORTANT: The tldr field must be a plain string with bullet points separated by newlines.
Do NOT pass tldr as a JSON array or list — it must be a single string value.

Do NOT produce a narrative, key findings, or participants list.
Focus on the essential outcome only.
Do NOT fetch external URLs unless critical.
IMPORTANT: At this level you MUST NOT follow any reference URLs.
Fetch only the root thread and produce your summary immediately."""


class BriefFinishAction(SummarizerFinishActionBase):
    """Finish action for brief summarization level."""

    tldr: str = Field(
        description="Bullet-point TL;DR of the conversation (2-3 key points). Must be a single string, not a list."
    )
    action_items: list[str] = Field(
        default_factory=list, description="Decisions, todos, follow-ups, or assignments mentioned"
    )

    @field_validator("tldr", mode="before")
    @classmethod
    def coerce_tldr_to_str(cls, v: object) -> str:
        """Coerce tldr to a string if the LLM returns a list."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)  # type: ignore[union-attr]
        return str(v) if not isinstance(v, str) else v


class BriefFinishTool(SummarizerFinishToolBase):
    """Tool for brief summarization completion."""

    @classmethod
    def _get_description(cls) -> str:
        return (
            "Call this tool when you have completed a brief summarization. "
            "This tool accepts only TL;DR (2-3 bullet points as a single newline-separated STRING, not a list) "
            "and action items. "
            "IMPORTANT: tldr must be a plain string. Do not pass a list or array for tldr. "
            "Do not include narrative, key findings, or participants."
        )

    @classmethod
    def create(cls, **kwargs: object) -> Sequence[BriefFinishTool]:
        return [
            BriefFinishTool(
                description=cls._get_description(),
                action_type=BriefFinishAction,
                observation_type=SummarizerFinishObservation,
                executor=SummarizerFinishExecutor(),
                annotations=ToolAnnotations(
                    title="finish",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


class BriefSummaryResult(SummaryResultBase):
    """Result of a brief summarization."""

    level: Literal["brief"] = "brief"
    tldr: str
    action_items: list[str] = Field(default_factory=list)

    def render_rich(self, console: Console) -> None:
        """Render the brief summary using rich typography.

        Args:
            console: A rich Console instance to write to.
        """
        tldr_header = Text("TL;DR", style="bold")
        console.print(tldr_header)
        console.print(_inline_bold(self.tldr))

        if self.action_items:
            console.print()
            console.print(Text("ACTION ITEMS", style="bold"))
            for item in self.action_items:
                t = _inline_bold(f"  □ {item}")
                t.stylize("magenta")
                console.print(t)

        self._render_metadata_footer(console)

    def __str__(self) -> str:
        """Pretty format the brief summary."""
        lines = [
            "=" * 70,
            "TL;DR",
            "=" * 70,
            self.tldr,
        ]

        if self.action_items:
            lines.extend(
                [
                    "",
                    "=" * 70,
                    "ACTION ITEMS",
                    "=" * 70,
                ]
            )
            for item in self.action_items:
                lines.append(f"  • {item}")

        lines.append(self._format_metadata_str())
        return "\n".join(lines)
