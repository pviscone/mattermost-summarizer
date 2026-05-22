"""Base classes for summarization levels."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from openhands.sdk import Action, Observation, TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition
from pydantic import BaseModel, Field
from rich.console import Console
from rich.text import Text


def _format_token_count(value: int) -> str:
    """Format a token count with K suffix for >= 1000."""
    if value >= 1000:
        return f"{value / 1000:.2f}K"
    return str(value)


def _inline_bold(s: str) -> Text:
    """Convert **...** markdown bold to a rich Text with bold spans."""
    markup = re.sub(r"\*\*(.+?)\*\*", r"[bold]\1[/bold]", s)
    return Text.from_markup(markup)


class SummaryMeta(BaseModel):
    """Metadata about a summary operation."""

    thread_length: int = 0
    cost: float = 0.0
    model_used: str = ""
    duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0


class SummaryResultBase(BaseModel):
    """Base class for all summarization result types."""

    metadata: SummaryMeta = SummaryMeta()

    def _render_metadata_footer(self, console: Console) -> None:
        """Render the metadata footer section (shared by all levels)."""
        console.print()
        console.print(Text("─" * 60, style="dim"))

        tokens_parts = [f"↑ input {_format_token_count(self.metadata.input_tokens)}"]

        cache_read = self.metadata.cache_read_tokens
        input_with_cache = self.metadata.input_tokens + cache_read
        if input_with_cache > 0 and cache_read > 0:
            cache_hit_pct = (cache_read / input_with_cache) * 100
            tokens_parts.append(f"cache hit {cache_hit_pct:.2f}%")

        if self.metadata.reasoning_tokens > 0:
            tokens_parts.append(f"reasoning {self.metadata.reasoning_tokens}")

        tokens_parts.append(f"↓ output {_format_token_count(self.metadata.output_tokens)}")
        tokens_parts.append(f"$ {self.metadata.cost:.2f}")

        meta_line = "  Tokens: " + " • ".join(tokens_parts)
        console.print(Text(meta_line, style="dim"))

    def _format_metadata_str(self) -> str:
        """Format metadata as plain text string (shared by all levels)."""
        lines = [
            "",
            "=" * 70,
            "METADATA",
            "=" * 70,
            f"  Thread length: {self.metadata.thread_length} posts",
            f"  Model: {self.metadata.model_used}",
            f"  Duration: {self.metadata.duration_seconds:.1f}s",
        ]

        tokens_parts = [f"↑ input {_format_token_count(self.metadata.input_tokens)}"]

        cache_read = self.metadata.cache_read_tokens
        input_with_cache = self.metadata.input_tokens + cache_read
        if input_with_cache > 0 and cache_read > 0:
            cache_hit_pct = (cache_read / input_with_cache) * 100
            tokens_parts.append(f"cache hit {cache_hit_pct:.2f}%")

        if self.metadata.reasoning_tokens > 0:
            tokens_parts.append(f"reasoning {self.metadata.reasoning_tokens}")

        tokens_parts.append(f"↓ output {_format_token_count(self.metadata.output_tokens)}")
        tokens_parts.append(f"$ {self.metadata.cost:.2f}")

        lines.append(f"  Tokens: {' • '.join(tokens_parts)}")
        return "\n".join(lines)


class SummarizerFinishActionBase(Action):
    """Base class for all summarizer finish actions.

    Provides a sentinel field for isinstance() checking.
    """

    is_summarizer_finish: Literal[True] = Field(default=True, exclude=True)


class SummarizerFinishObservation(Observation):
    """Result of a finish action."""

    success: bool = True
    summary_provided: bool = True

    @property
    def to_llm_content(self) -> list[TextContent]:
        return [TextContent(text="Summary complete. Thank you!")]


class SummarizerFinishExecutor(ToolExecutor[SummarizerFinishActionBase, SummarizerFinishObservation]):
    """Executor for the finish tool.

    This is a terminal action - the real work happens in summarizer.py
    which extracts the finish action from conversation events.
    """

    def __call__(
        self, action: SummarizerFinishActionBase, conversation: object | None = None
    ) -> SummarizerFinishObservation:
        return SummarizerFinishObservation(success=True, summary_provided=True)


class SummarizerFinishToolBase(ToolDefinition[SummarizerFinishActionBase, SummarizerFinishObservation]):
    """Base class for level-specific finish tools."""

    name = "finish"

    @classmethod
    def create(cls, **kwargs: object) -> Sequence[SummarizerFinishToolBase]:
        return [
            cls(
                description=cls._get_description(),
                action_type=SummarizerFinishActionBase,
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

    @classmethod
    def _get_description(cls) -> str:
        raise NotImplementedError("Subclasses must implement _get_description()")
