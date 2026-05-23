"""Normal summarization level - full summary with narrative and participants."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from openhands.sdk.tool.tool import ToolAnnotations
from pydantic import Field, field_validator
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from mattermost_summarizer.levels.base import (
    SummarizerFinishActionBase,
    SummarizerFinishExecutor,
    SummarizerFinishObservation,
    SummarizerFinishToolBase,
    SummaryMeta,
    SummaryResultBase,
)
from mattermost_summarizer.levels.base import (
    inline_bold as _inline_bold,
)

USER_MESSAGE_ADDENDUM = """Level: NORMAL (standard)

Produce a complete summary with:
- TL;DR: 3-5 bullet points capturing key outcomes (as a newline-separated STRING — not a list or array)
- Key Findings: Important insights (as a list of strings)
- Narrative: Chronological walkthrough of the conversation (as a single string)
- Action Items: Decisions, todos, follow-ups (as a list of strings)
- Participants: List of contributors (as a list of strings)

IMPORTANT: The tldr field must be a plain string with bullet points separated by newlines.
Do NOT pass tldr as a JSON array or list — it must be a single string value.

This is the default summarization level. Be thorough and balanced."""


class NormalFinishAction(SummarizerFinishActionBase):
    """Finish action for normal summarization level."""

    tldr: str = Field(
        description="Bullet-point TL;DR of the conversation (3-5 key points). Must be a single string, not a list."
    )
    key_findings: list[str] = Field(
        default_factory=list, description="Key findings or insights discovered in the conversation"
    )
    narrative: str = Field(description="Chronological narrative of the conversation, noting who said what")
    action_items: list[str] = Field(
        default_factory=list, description="Decisions, todos, follow-ups, or assignments mentioned"
    )
    participants: list[str] = Field(default_factory=list, description="People who contributed to the thread")

    @field_validator("tldr", mode="before")
    @classmethod
    def coerce_tldr_to_str(cls, v: object) -> str:
        """Coerce tldr to a string if the LLM returns a list."""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)  # type: ignore[union-attr]
        return str(v) if not isinstance(v, str) else v


class NormalFinishTool(SummarizerFinishToolBase):
    """Tool for normal summarization completion."""

    @classmethod
    def _get_description(cls) -> str:
        return (
            "Call this tool when you have completed a normal summarization. "
            "This tool accepts TL;DR (3-5 bullet points as a single newline-separated STRING, not a list), "
            "key findings, narrative, action items, and participants. "
            "IMPORTANT: tldr must be a plain string. Do not pass a list or array for tldr."
        )

    @classmethod
    def create(cls, **kwargs: object) -> Sequence[NormalFinishTool]:
        return [
            NormalFinishTool(
                description=cls._get_description(),
                action_type=NormalFinishAction,
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


class NormalSummaryResult(SummaryResultBase):
    """Result of a normal summarization."""

    level: Literal["normal"] = "normal"
    tldr: str
    key_findings: list[str] = Field(default_factory=list)
    narrative: str
    action_items: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    metadata: SummaryMeta = SummaryMeta()

    def render_rich(self, console: Console) -> None:
        """Render the normal summary using rich typography.

        Args:
            console: A rich Console instance to write to.
        """
        tldr_header = Text("TL;DR", style="bold")
        console.print(tldr_header)
        console.print(_inline_bold(self.tldr))

        if self.key_findings:
            console.print()
            console.print(Text("KEY FINDINGS", style="bold"))
            for finding in self.key_findings:
                t = _inline_bold(f"  ● {finding}")
                t.stylize("cyan")
                console.print(t)

        console.print()
        console.print(Text("NARRATIVE", style="bold"))
        md = Markdown(self.narrative, code_theme="none")
        console.print(md)

        if self.action_items:
            console.print()
            console.print(Text("ACTION ITEMS", style="bold"))
            for item in self.action_items:
                t = _inline_bold(f"  □ {item}")
                t.stylize("magenta")
                console.print(t)

        if self.participants:
            console.print()
            console.print(Text("PARTICIPANTS", style="bold"))
            console.print(", ".join(self.participants))

        self._render_metadata_footer(console)

    def __str__(self) -> str:
        """Pretty format the normal summary."""
        lines = [
            "=" * 70,
            "TL;DR",
            "=" * 70,
            self.tldr,
        ]

        if self.key_findings:
            lines.extend(
                [
                    "",
                    "=" * 70,
                    "KEY FINDINGS",
                    "=" * 70,
                ]
            )
            for finding in self.key_findings:
                lines.append(f"  • {finding}")

        lines.extend(
            [
                "",
                "=" * 70,
                "NARRATIVE",
                "=" * 70,
                self.narrative,
            ]
        )

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

        if self.participants:
            lines.extend(
                [
                    "",
                    "=" * 70,
                    "PARTICIPANTS",
                    "=" * 70,
                    ", ".join(self.participants),
                ]
            )

        lines.append(self._format_metadata_str())
        return "\n".join(lines)
