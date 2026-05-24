"""Fetch reference tool for orchestrator (consolidates tracking and delegation)."""

from __future__ import annotations

import itertools
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from openhands.sdk import Action, Observation
from openhands.sdk.llm.message import TextContent
from openhands.sdk.tool import ToolExecutor
from openhands.sdk.tool.tool import DeclaredResources, ToolDefinition

if TYPE_CHECKING:
    from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

logger = logging.getLogger(__name__)


class FetchReferenceAction(Action):
    """Action to safely fetch a reference URL."""

    url: str


class FetchReferenceObservation(Observation):
    """Observation from fetching a reference."""

    result: str
    error: str | None = None

    @property
    def to_llm_content(self) -> Sequence[TextContent]:
        if self.error:
            return [TextContent(text=f"Error: {self.error}")]
        return [TextContent(text=self.result)]


class FetchReferenceExecutor(ToolExecutor[FetchReferenceAction, FetchReferenceObservation]):
    """Executor for fetching references (handles cycle tracking + sub-agent delegation)."""

    def __init__(self, tracker: ReferenceTracker | None = None, max_children: int = 20) -> None:
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        self._tracker = tracker or ReferenceTracker()

        # We instantiate a DelegateExecutor to handle the sub-agent interaction
        from openhands.tools.delegate.impl import DelegateExecutor

        self._delegate_executor = DelegateExecutor(max_children=max_children)
        self._agent_counter = itertools.count()

    def __call__(self, action: FetchReferenceAction, conversation: object | None = None) -> FetchReferenceObservation:
        if not action.url:
            return FetchReferenceObservation(result="", error="URL required")

        from mattermost_summarizer.tools.reference_tracker import ReferenceType, classify_url_full

        # Classify first to fail-fast on unknown URLs
        classified = classify_url_full(action.url)
        if classified.reference_type == ReferenceType.UNKNOWN:
            return FetchReferenceObservation(result="", error="Unsupported URL type. Cannot follow.")

        # Depth-based check (per-URL, not global counter)
        with self._tracker.lock():
            if self._tracker.has_been_followed(action.url):
                return FetchReferenceObservation(result="", error="URL has already been followed (cycle prevented).")

            url_depth = self._tracker.get_depth_for(action.url)
            # Root URLs (never registered) are always allowed
            effective_depth = url_depth if url_depth is not None else 0
            if url_depth is not None and url_depth >= self._tracker.max_depth:
                return FetchReferenceObservation(
                    result="", error=f"Maximum reference depth ({self._tracker.max_depth}) reached."
                )
            # When max_depth=0, only the root URL may be fetched; reject unregistered URLs afterward
            if url_depth is None and self._tracker.max_depth == 0 and len(self._tracker.followed_urls) > 0:
                return FetchReferenceObservation(
                    result="", error="No reference following allowed at this summary level (max_depth=0)."
                )

        # Spawn the appropriate sub-agent with a unique ID
        from openhands.tools.delegate.definition import DelegateAction

        agent_id = f"subagent_{classified.agent_type}_{next(self._agent_counter)}"

        spawn_action = DelegateAction(command="spawn", ids=[agent_id], agent_types=[classified.agent_type])
        spawn_obs = self._delegate_executor(spawn_action, conversation)  # type: ignore
        if getattr(spawn_obs, "is_error", False):
            return FetchReferenceObservation(
                result="", error=f"Failed to spawn sub-agent: {spawn_obs.to_llm_content[0].text}"
            )

        # Delegate the task to the spawned agent
        task_desc = (
            f"Fetch and summarize this reference: {action.url}\n"
            "Return the full relevant content, any attachments/links, "
            "and highlight important patches/logs/context."
        )
        delegate_action = DelegateAction(command="delegate", tasks={agent_id: task_desc})
        delegate_obs = self._delegate_executor(delegate_action, conversation)  # type: ignore

        result_text = "\n".join(c.text for c in delegate_obs.to_llm_content if hasattr(c, "text"))

        # Mark this URL as followed at its effective depth
        self._tracker.mark_followed(action.url, effective_depth)

        # Scan the sub-agent's result for new followable URLs.
        # Pre-register each at child depth before building the block.
        from mattermost_summarizer.tools.reference_tracker import (
            build_reference_following_prompt,
            classify_urls_in_text,
            extract_sentence_context,
        )

        followable = classify_urls_in_text(result_text, self._tracker)
        child_depth = effective_depth + 1

        if followable and child_depth < self._tracker.max_depth:
            # Register each followable URL at child_depth (pre-registration)
            for ref in followable:
                self._tracker.register_pending(ref.url, child_depth)

            # Extract sentence context for each URL
            context_sentences = {ref.url: extract_sentence_context(result_text, ref.url) for ref in followable}

            ref_block = build_reference_following_prompt(
                followable, self._tracker, parent_depth=effective_depth, context_sentences=context_sentences
            )
            full_result = f"{result_text}\n\n---\nReferences found in result:\n{ref_block}"
        else:
            full_result = result_text

        return FetchReferenceObservation(result=full_result)


class FetchReferenceTool(ToolDefinition[FetchReferenceAction, FetchReferenceObservation]):
    """Tool for fetching a reference URL, safely handling depth/cycle tracking."""

    name = "fetch_reference"

    def declared_resources(self, action: FetchReferenceAction) -> DeclaredResources:  # type: ignore[override]
        # Each URL fetch is independent; lock on the URL to prevent duplicate fetches
        # of the same URL, but allow different URLs to run concurrently.
        return DeclaredResources(keys=(f"url:{action.url}",), declared=True)

    @classmethod
    def create(
        cls, tracker: ReferenceTracker | None = None, max_children: int = 20, **kwargs: object
    ) -> Sequence[FetchReferenceTool]:
        return [
            cls(
                description=(
                    "Fetch a reference URL. "
                    "Automatically checks if the URL was already followed to prevent cycles, "
                    "verifies depth limits, and delegates to the appropriate sub-agent to fetch the content. "
                    "Returns the summarized content of the reference, or an error if it cannot be followed."
                ),
                action_type=FetchReferenceAction,
                observation_type=FetchReferenceObservation,
                executor=FetchReferenceExecutor(tracker, max_children=max_children),
            )
        ]


__all__ = [
    "FetchReferenceTool",
    "FetchReferenceAction",
    "FetchReferenceObservation",
    "FetchReferenceExecutor",
]
