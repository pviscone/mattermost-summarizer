"""Main summarizer module for mattermost-summarizer."""

from __future__ import annotations

import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path

from openhands.sdk import LocalConversation

from mattermost_summarizer.agent import SYSTEM_PROMPT, build_orchestrator_agent
from mattermost_summarizer.client import MattermostClient
from mattermost_summarizer.config import MattermostSummarizerConfig
from mattermost_summarizer.critic import SummarizationCritic
from mattermost_summarizer.exceptions import (
    AgentStuckError,
    PermalinkError,
)
from mattermost_summarizer.levels import (
    BRIEF_ADDENDUM,
    DETAILED_ADDENDUM,
    NORMAL_ADDENDUM,
    AnySummaryResult,
    BriefSummaryResult,
    DetailedSummaryResult,
    NormalSummaryResult,
    SummarizerFinishActionBase,
    SummaryLevel,
    SummaryMeta,
)
from mattermost_summarizer.sanitization import format_with_delimiter
from mattermost_summarizer.subagents import register_subagents
from mattermost_summarizer.tools.fetch_thread.impl import FetchThreadAction, FetchThreadExecutor
from mattermost_summarizer.tools.reference_tracker import (
    ClassifiedUrl,
    ReferenceTracker,
)
from mattermost_summarizer.utils import parse_channel_url, parse_permalink, parse_time_point
from mattermost_summarizer.visualizer import FileConversationVisualizer


class MattermostSummarizer:
    """High-level API for summarizing Mattermost conversation threads.

    Example usage:
        summarizer = MattermostSummarizer.from_config("mattermost-summarizer.toml")
        result = summarizer.summarize("https://chat.canonical.com/canonical/pl/abc123xyz")
        print(result)

    Or with environment variables:
        summarizer = MattermostSummarizer.from_env()
        result = summarizer.summarize("https://chat.example.com/team/pl/post123")
        print(result.tldr)
    """

    def __init__(self, config: MattermostSummarizerConfig) -> None:
        self.config = config

    @classmethod
    def from_config(cls, path: Path | str) -> MattermostSummarizer:
        """Load configuration from a TOML file.

        Args:
            path: Path to TOML config file

        Returns:
            MattermostSummarizer instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ConfigError: If config is invalid
        """
        config = MattermostSummarizerConfig.from_config(path)
        return cls(config)

    @classmethod
    def from_env(cls) -> MattermostSummarizer:
        """Load configuration from environment variables.

        Returns:
            MattermostSummarizer instance
        """
        config = MattermostSummarizerConfig.from_env()
        return cls(config)

    def summarize(
        self,
        permalink_url: str,
        level: SummaryLevel = SummaryLevel.NORMAL,
        prompt: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> AnySummaryResult:
        """Summarize a Mattermost thread or channel window.

        Args:
            permalink_url: A Mattermost permalink, or a Mattermost channel URL when
                start_time and end_time are provided.
            level: Summarization detail level (default: NORMAL)
            prompt: Optional custom prompt appended to the default prompt
            start_time: Inclusive start time for channel-window mode (ISO 8601)
            end_time: Inclusive end time for channel-window mode (ISO 8601)

        Returns:
            AnySummaryResult (BriefSummaryResult, NormalSummaryResult, or DetailedSummaryResult)
                with tldr, narrative (if not brief), action_items, participants (if not brief), and metadata

        Raises:
            PermalinkError: If URL format is invalid
            AuthenticationError: If Mattermost API returns 401
            ThreadNotFoundError: If thread doesn't exist (404)
            AgentStuckError: If agent gets stuck and cannot complete
        """
        start_clock = time.time()

        if (start_time is None) != (end_time is None):
            raise ValueError("start_time and end_time must be provided together")

        is_channel_window = start_time is not None and end_time is not None
        window_start: datetime | None = None
        window_end: datetime | None = None
        if is_channel_window:
            window_start = parse_time_point(start_time)
            window_end = parse_time_point(end_time)
            if window_start > window_end:
                raise ValueError("start_time must be earlier than or equal to end_time")

        try:
            if is_channel_window:
                team_name, channel_name = parse_channel_url(permalink_url)
            else:
                post_id = parse_permalink(permalink_url)
        except ValueError as e:
            raise PermalinkError(str(e)) from e

        _addendum_by_level: dict[SummaryLevel, str] = {
            SummaryLevel.BRIEF: BRIEF_ADDENDUM,
            SummaryLevel.NORMAL: NORMAL_ADDENDUM,
            SummaryLevel.DETAILED: DETAILED_ADDENDUM,
        }
        level_addendum = _addendum_by_level[level]

        visualizer = FileConversationVisualizer("agent-trace.log")

        with (
            MattermostClient(
                base_url=str(self.config.mattermost_url),
                token=self.config.mattermost_token.get_secret_value(),
            ) as client,
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            from mattermost_summarizer.ssrf import set_ssrf_defaults

            set_ssrf_defaults(
                blocked_ips=self.config.ssrf_blocked_ips,
                blocked_hostnames=self.config.ssrf_blocked_hostnames,
                log_blocked=self.config.ssrf_log_blocked,
            )

            conversation_length = 1
            if is_channel_window:
                assert window_start is not None and window_end is not None
                channel = client.get_channel_by_name(team_name, channel_name)
                channel_posts = [
                    post
                    for post in client.get_channel_posts(channel.id)
                    if window_start <= post.created_at <= window_end
                ]
                if not channel_posts:
                    raise AgentStuckError("No messages were found in the selected channel time window.")

                conversation_length = len(channel_posts)

                all_user_ids = {post.author_id for post in channel_posts if post.author_id}
                user_cache: dict[str, str] = {}
                for user_id in all_user_ids:
                    try:
                        user = client.get_user(user_id)
                        user_cache[user_id] = user.username
                    except Exception:
                        user_cache[user_id] = user_id

                chat_lines = [
                    f"Channel: #{channel.name}" + (f" ({channel.display_name})" if channel.display_name else ""),
                    f"Time window: {window_start.isoformat()} to {window_end.isoformat()}",
                    "=" * 50,
                ]
                for index, post in enumerate(channel_posts, 1):
                    author = user_cache.get(post.author_id, post.author_id)
                    kind = "Reply" if post.root_id and post.root_id != post.id else "Post"
                    chat_lines.append(f"{index}. {kind} by @{author} at {post.created_at.isoformat()}:")
                    chat_lines.append(f"  {post.message}")
                    chat_lines.append("")

                conversation_text = format_with_delimiter("\n".join(chat_lines))
                intro = (
                    f"Summarize this Mattermost chat window for channel #{channel.name}.\n"
                    f"The time window is {window_start.isoformat()} to {window_end.isoformat()}.\n"
                    "All messages are included in chronological order, including posts and replies."
                )
            else:
                # Prefetch root thread before initializing the LLM.
                fetch_executor = FetchThreadExecutor(client)
                fetch_obs = fetch_executor(FetchThreadAction(post_id=post_id))
                if fetch_obs.error:
                    raise AgentStuckError(f"Failed to fetch root thread: {fetch_obs.error}")

                conversation_length = int(fetch_obs.total_replies) + 1
                conversation_text = format_with_delimiter("\n".join(item.text for item in fetch_obs.to_llm_content))
                intro = f"Summarize this Mattermost thread. The post ID is: {post_id}"

            prompt_sections = [intro, SYSTEM_PROMPT]
            if prompt:
                prompt_sections.append(prompt)
            prompt_sections.append(level_addendum)
            message = "\n\n".join(prompt_sections) + f"\n\n{conversation_text}"

            register_subagents(client)

            critic = None
            if self.config.critic_enabled:
                critic = SummarizationCritic(
                    llm_model=self.config.llm_model,
                    llm_api_key=self.config.llm_api_key.get_secret_value(),
                    llm_base_url=self.config.llm_base_url,
                    level=level,
                )

            _depth_by_level: dict[SummaryLevel, int] = {
                SummaryLevel.BRIEF: 0,
                SummaryLevel.NORMAL: 1,
                SummaryLevel.DETAILED: 3,
            }
            effective_depth = (
                self.config.max_reference_depth
                if self.config.max_reference_depth is not None
                else _depth_by_level[level]
            )

            tracker = ReferenceTracker(max_depth=effective_depth)
            tracker.mark_followed(permalink_url, 0)

            agent = build_orchestrator_agent(
                llm_model=self.config.llm_model,
                llm_api_key=self.config.llm_api_key.get_secret_value(),
                llm_base_url=self.config.llm_base_url,
                level=level,
                max_reference_depth=effective_depth,
                max_sub_agents=self.config.max_sub_agents,
                critic=critic,
                tracker=tracker,
            )

            conv_ref: list[LocalConversation | None] = [None]
            finish_seen_ref = [False]

            def _on_finish_callback(event: object) -> None:
                if (
                    not finish_seen_ref[0]
                    and hasattr(event, "action")
                    and isinstance(getattr(event, "action", None), SummarizerFinishActionBase)
                    and conv_ref[0] is not None
                ):
                    finish_seen_ref[0] = True
                    conv_ref[0].pause()

            # NOTE: The Python-side pause-and-inject loop (pause_callback + URL injection) has
            # been removed.  Reference injection is now handled transparently inside
            # FetchReferenceExecutor — it appends the "References found" block directly to the
            # tool observation that the orchestrator LLM receives.
            conversation = LocalConversation(
                agent=agent,
                workspace=tmpdir,
                visualizer=visualizer,
                callbacks=[_on_finish_callback],
            )
            conv_ref[0] = conversation

            conversation.send_message(message)  # type: ignore[arg-type, misc]

            max_delegation_iterations = 20
            for _iteration in range(max_delegation_iterations):
                if finish_seen_ref[0]:
                    break
                conversation.run()  # type: ignore[misc]

                if finish_seen_ref[0]:
                    break
            else:
                logging.getLogger(__name__).warning(
                    "Summarization loop reached max iterations (%d) without finishing.",
                    max_delegation_iterations,
                )

            try:
                finish_action = _extract_finish_action(conversation)

                if finish_action is None:
                    if conversation.stuck_detector and conversation.stuck_detector.is_stuck():
                        raise AgentStuckError(
                            "Agent got stuck and could not complete the summarization. "
                            "This may be due to repeated actions or context issues."
                        )
                    raise AgentStuckError("Agent did not produce a finish action. The summary could not be extracted.")

                duration = time.time() - start_clock

                input_tokens = 0
                output_tokens = 0
                cache_read_tokens = 0
                cache_write_tokens = 0
                reasoning_tokens = 0

                combined_metrics = conversation.conversation_stats.get_combined_metrics()
                cost = combined_metrics.accumulated_cost
                token_usage = combined_metrics.accumulated_token_usage
                if token_usage:
                    input_tokens = (
                        getattr(token_usage, "prompt_tokens", 0) or getattr(token_usage, "input_tokens", 0) or 0
                    )
                    output_tokens = (
                        getattr(token_usage, "completion_tokens", 0) or getattr(token_usage, "output_tokens", 0) or 0
                    )
                    cache_read_tokens = getattr(token_usage, "cache_read_tokens", 0) or 0
                    cache_write_tokens = getattr(token_usage, "cache_write_tokens", 0) or 0
                    reasoning_tokens = getattr(token_usage, "reasoning_tokens", 0) or 0

                thread_length = 1
                if hasattr(finish_action, "tldr"):
                    thread_length = conversation_length

                metadata = SummaryMeta(
                    thread_length=thread_length,
                    cost=cost,
                    model_used=self.config.llm_model,
                    duration_seconds=duration,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    reasoning_tokens=reasoning_tokens,
                )

                tldr = getattr(finish_action, "tldr", "")
                action_items = getattr(finish_action, "action_items", [])
                key_findings = getattr(finish_action, "key_findings", [])
                narrative = getattr(finish_action, "narrative", "")
                participants = getattr(finish_action, "participants", [])

                if level == SummaryLevel.BRIEF:
                    return BriefSummaryResult(
                        tldr=tldr,
                        action_items=action_items,
                        metadata=metadata,
                    )
                elif level == SummaryLevel.DETAILED:
                    return DetailedSummaryResult(
                        tldr=tldr,
                        key_findings=key_findings,
                        narrative=narrative,
                        action_items=action_items,
                        participants=participants,
                        open_questions=getattr(finish_action, "open_questions", []),
                        context_sources=getattr(finish_action, "context_sources", []),
                        metadata=metadata,
                    )
                else:
                    return NormalSummaryResult(
                        tldr=tldr,
                        key_findings=key_findings,
                        narrative=narrative,
                        action_items=action_items,
                        participants=participants,
                        metadata=metadata,
                    )
            finally:
                conversation.close()
                visualizer.close()


# _PauseAfterDelegationCallback and _make_pause_after_delegation_callback have been
# removed.  Reference injection is now done inside FetchReferenceExecutor; the
# Python-side pause-and-inject loop is no longer needed.


def _extract_finish_action(conversation: LocalConversation) -> SummarizerFinishActionBase | None:
    """Scan conversation events for a SummarizerFinishAction."""
    if not hasattr(conversation, "state") or not conversation.state:
        return None

    events = getattr(conversation.state, "events", [])

    for event in reversed(events):
        if hasattr(event, "action") and event.action is not None:
            action = event.action
            if isinstance(action, SummarizerFinishActionBase):
                return action

        if hasattr(event, "observation") and event.observation is not None:
            obs = event.observation
            if hasattr(obs, "success") and hasattr(obs, "summary_provided"):
                if obs.summary_provided:
                    for prev_event in reversed(events):
                        if hasattr(prev_event, "action") and prev_event.action is not None:
                            prev_action = prev_event.action
                            if isinstance(prev_action, SummarizerFinishActionBase):
                                return prev_action

    return None


# _extract_last_delegate_observation has been removed — no longer used after the
# Python-side URL-injection loop was replaced by FetchReferenceExecutor's built-in injection.


def format_url_injection_message(
    classified_urls: list[ClassifiedUrl],
    tracker: ReferenceTracker,
) -> str:
    """Format the classified URL list as an injected user message."""
    if not classified_urls:
        return ""

    lines: list[str] = ["References found in delegation result:"]
    for i, ref in enumerate(classified_urls, 1):
        lines.append(f"{i}. {ref.url}  ({ref.reference_type.value} -> {ref.agent_type})")

    followed_count = len(tracker.followed_urls)
    depth_status = "can follow more" if followed_count < tracker.max_depth else "max depth reached"
    lines.append(f"URLs followed: {followed_count}/{tracker.max_depth} — {depth_status}")
    lines.append("")
    lines.append("Decide which (if any) are relevant and call follow_url before delegating.")

    return "\n".join(lines)
