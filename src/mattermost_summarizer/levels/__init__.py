"""Summarization levels package.

Provides three levels of summarization detail:
- brief: TL;DR + action items only
- normal: Full summary with narrative and participants
- detailed: Full summary + open questions + context sources
"""

from __future__ import annotations

from enum import Enum

from mattermost_summarizer.levels.base import (
    SummarizerFinishActionBase,
    SummarizerFinishExecutor,
    SummarizerFinishObservation,
    SummaryMeta,
    SummaryResultBase,
)
from mattermost_summarizer.levels.brief import (
    USER_MESSAGE_ADDENDUM as BRIEF_ADDENDUM,
)
from mattermost_summarizer.levels.brief import (
    BriefFinishAction,
    BriefFinishTool,
    BriefSummaryResult,
)
from mattermost_summarizer.levels.detailed import (
    USER_MESSAGE_ADDENDUM as DETAILED_ADDENDUM,
)
from mattermost_summarizer.levels.detailed import (
    DetailedFinishAction,
    DetailedFinishTool,
    DetailedSummaryResult,
)
from mattermost_summarizer.levels.normal import (
    USER_MESSAGE_ADDENDUM as NORMAL_ADDENDUM,
)
from mattermost_summarizer.levels.normal import (
    NormalFinishAction,
    NormalFinishTool,
    NormalSummaryResult,
)


class SummaryLevel(Enum):
    """Summarization detail level."""

    BRIEF = "brief"
    NORMAL = "normal"
    DETAILED = "detailed"


AnySummaryResult = BriefSummaryResult | NormalSummaryResult | DetailedSummaryResult

__all__ = [
    "SummaryLevel",
    "AnySummaryResult",
    "SummaryResultBase",
    "SummaryMeta",
    "SummarizerFinishActionBase",
    "SummarizerFinishObservation",
    "SummarizerFinishExecutor",
    "BriefSummaryResult",
    "BriefFinishAction",
    "BriefFinishTool",
    "BRIEF_ADDENDUM",
    "NormalSummaryResult",
    "NormalFinishAction",
    "NormalFinishTool",
    "NORMAL_ADDENDUM",
    "DetailedSummaryResult",
    "DetailedFinishAction",
    "DetailedFinishTool",
    "DETAILED_ADDENDUM",
]
