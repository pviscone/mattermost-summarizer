"""LLM-based critic for iterative summary refinement."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from openhands.sdk.critic import CriticBase, CriticResult, IterativeRefinementConfig
from openhands.sdk.event import LLMConvertibleEvent
from openhands.sdk.llm.message import Message, TextContent
from pydantic import BaseModel, Field

from mattermost_summarizer.levels import SummarizerFinishActionBase, SummaryLevel


class CriticEvaluation(BaseModel):
    """Result from LLM critic evaluation."""

    score: float = Field(description="Quality score between 0.0 and 1.0")
    feedback: str = Field(description="Detailed feedback on what's missing or wrong")


class SummarizationCritic(CriticBase):
    """LLM-based critic for evaluating and refining summarization quality.

    This critic:
    1. Extracts thread content and gathered context from conversation events
    2. Extracts the produced summary from the finish action
    3. Evaluates quality using an LLM with level-specific rubric
    4. Returns CriticResult with score and actionable feedback
    """

    llm_model: str = Field(description="LLM model for critic evaluation")
    llm_api_key: str = Field(description="API key for LLM")
    llm_base_url: str | None = Field(default=None, description="Optional base URL for LLM")
    level: SummaryLevel = Field(default=SummaryLevel.NORMAL, description="Summarization level")
    iterative_refinement: IterativeRefinementConfig | None = Field(
        default_factory=lambda: IterativeRefinementConfig(
            success_threshold=0.7,
            max_iterations=2,
        ),
        description="Iterative refinement configuration",
    )

    _rubric_templates: ClassVar[dict[str, str]] = {
        "brief": """Evaluate whether the brief summary (TL;DR + action items) captures:
1. Key outcomes - Are the 2-3 bullet points the most important takeaways?
2. Conciseness - Is the summary appropriately terse without fluff?
3. Action items - Are decisions, todos, and follow-ups captured?
4. Completeness - Despite brevity, are essential details present?

Score guide:
- 0.9-1.0: Excellent - captures all key outcomes concisely
- 0.7-0.9: Good - captures most key points, minor omissions
- 0.5-0.7: Fair - missing important outcomes or overly verbose
- Below 0.5: Poor - fails to capture key points or missing action items""",
        "normal": """Evaluate whether the summary captures:
1. TL;DR - 3-5 key bullet points capturing essential outcomes
2. Key Findings - Important insights discovered
3. Narrative - Chronological walkthrough with who said what
4. Action Items - Decisions, todos, follow-ups
5. Participants - Who contributed to the thread

Score guide:
- 0.9-1.0: Excellent - all components complete and accurate
- 0.7-0.9: Good - all components present, minor quality issues
- 0.5-0.7: Fair - missing components or inaccurate details
- Below 0.5: Poor - fails to capture essential information""",
        "detailed": """Evaluate whether the detailed summary captures:
1. TL;DR - 3-5 key bullet points
2. Key Findings - Important insights
3. Narrative - Detailed chronological walkthrough noting contributions
4. Action Items - All decisions and follow-ups
5. Participants - Full list of contributors
6. Open Questions - Unresolved issues needing follow-up
7. Context Sources - URLs and references mentioned

Score guide:
- 0.9-1.0: Excellent - all components thorough and accurate
- 0.7-0.9: Good - all components present, some missing nuance
- 0.5-0.7: Fair - missing open questions or context sources
- Below 0.5: Poor - incomplete or inaccurate summary""",
    }

    def evaluate(
        self,
        events: Sequence[LLMConvertibleEvent],
        git_patch: str | None = None,
    ) -> CriticResult:
        """Evaluate the summary quality.

        Args:
            events: Conversation events to extract context and summary from
            git_patch: Optional git patch (not used for summarization)

        Returns:
            CriticResult with score (0-1) and feedback message
        """
        context = self._extract_gathered_context(events)
        summary = self._extract_finish_action(events)

        if not summary:
            return CriticResult(
                score=0.0,
                message="No summary found. The orchestrator did not produce a finish action.",
            )

        rubric = self._build_rubric(self.level)
        evaluation = self._call_critic_llm(context, summary, rubric)

        return CriticResult(
            score=evaluation.score,
            message=evaluation.feedback,
        )

    def _extract_gathered_context(self, events: Sequence[LLMConvertibleEvent]) -> str:
        """Extract gathered context from delegation results.

        Args:
            events: Conversation events

        Returns:
            Formatted string of all gathered context
        """
        context_parts: list[str] = []
        for event in events:
            obs = getattr(event, "observation", None)
            if obs is not None:
                to_llm_content = getattr(obs, "to_llm_content", None)
                if to_llm_content is not None:
                    content = to_llm_content()
                    if hasattr(content, "text") and isinstance(content.text, str):
                        if len(content.text) > 50:
                            context_parts.append(content.text)
                outputs = getattr(obs, "outputs", None)
                if isinstance(outputs, dict):
                    for agent_id, output in outputs.items():  # type: ignore[union-attr]
                        output_str = str(output)  # type: ignore[str-call]
                        if output and len(output_str) > 50:
                            context_parts.append(f"[{agent_id}]: {output_str}")

        if not context_parts:
            return "No additional context gathered - only root thread available."
        return "\n\n".join(context_parts)

    def _extract_finish_action(self, events: Sequence[LLMConvertibleEvent]) -> SummarizerFinishActionBase | None:
        """Extract the summarizer finish action from events.

        Args:
            events: Conversation events

        Returns:
            SummarizerFinishActionBase if found, None otherwise
        """
        for event in reversed(events):
            action = getattr(event, "action", None)
            if action is not None and isinstance(action, SummarizerFinishActionBase):
                return action
        return None

    def _build_rubric(self, level: SummaryLevel) -> str:
        """Build the evaluation rubric for the given level.

        Args:
            level: Summarization level

        Returns:
            Rubric prompt string
        """
        level_key = level.value
        return self._rubric_templates.get(level_key, self._rubric_templates["normal"])

    def _call_critic_llm(
        self,
        context: str,
        summary: SummarizerFinishActionBase,
        rubric: str,
    ) -> CriticEvaluation:
        """Call the LLM to evaluate the summary.

        Args:
            context: Gathered context from delegation
            summary: The produced summary to evaluate
            rubric: Level-specific evaluation rubric

        Returns:
            CriticEvaluation with score and feedback
        """
        import json

        from openhands.sdk import LLM
        from pydantic import SecretStr

        llm_kwargs: dict[str, Any] = {
            "model": self.llm_model,
            "api_key": SecretStr(self.llm_api_key),
        }
        if self.llm_base_url:
            llm_kwargs["base_url"] = self.llm_base_url

        llm = LLM(**llm_kwargs)

        summary_fields = {
            "tldr": getattr(summary, "tldr", ""),
            "key_findings": getattr(summary, "key_findings", []),
            "narrative": getattr(summary, "narrative", ""),
            "action_items": getattr(summary, "action_items", []),
            "participants": getattr(summary, "participants", []),
        }
        if self.level == SummaryLevel.DETAILED:
            summary_fields["open_questions"] = getattr(summary, "open_questions", [])
            summary_fields["context_sources"] = getattr(summary, "context_sources", [])

        prompt = f"""You are an expert summarization critic. Evaluate the following summary against the rubric.

## Rubric
{rubric}

## Original Context (gathered from delegation)
{context}

## Summary to Evaluate
{json.dumps(summary_fields, indent=2)}

## Your Task
Evaluate the summary and return a JSON object with:
{{
    "score": <quality score 0.0-1.0>,
    "feedback": "<specific, actionable feedback about what's missing or wrong>"
}}

Be critical but fair. Focus on substance over form. Consider:
- Does the TL;DR capture the most important outcomes?
- Are action items and decisions clearly identified?
- Is the narrative accurate and complete?
- Are participants correctly attributed?

Return ONLY valid JSON, no additional text."""

        try:
            response = llm.completion(messages=[Message(role="user", content=[TextContent(text=prompt)])])  # type: ignore[return-value]
            message = response.message
            content_items = message.content
            first_content = content_items[0] if content_items else None
            if first_content is not None and hasattr(first_content, "text"):
                response_text = str(first_content.text) if first_content.text else ""  # type: ignore[union-attr]
            else:
                response_text = ""

            stripped = response_text.strip()  # type: ignore[union-attr]
            if stripped.startswith("```json"):
                stripped = stripped[7:]
            elif stripped.startswith("```"):
                stripped = stripped[3:]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
            final_text = stripped.strip()

            result = json.loads(final_text)
            return CriticEvaluation(
                score=max(0.0, min(1.0, float(result.get("score", 0.5)))),
                feedback=str(result.get("feedback", "No feedback provided.")),
            )
        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            return CriticEvaluation(
                score=0.5,
                feedback=f"Critic evaluation failed due to parsing error: {e}. Assuming fair quality.",
            )


__all__ = [
    "SummarizationCritic",
    "CriticEvaluation",
]
