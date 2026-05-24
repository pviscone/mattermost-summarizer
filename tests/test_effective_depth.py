"""Tests for dynamic effective_depth logic in MattermostSummarizer.summarize().

Verifies that the ReferenceTracker receives the correct max_depth depending on
the summary level and whether max_reference_depth is explicitly configured.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl, SecretStr

from mattermost_summarizer.config import MattermostSummarizerConfig
from mattermost_summarizer.levels import SummaryLevel
from mattermost_summarizer.summarizer import MattermostSummarizer
from mattermost_summarizer.tools.fetch_thread.impl import FetchThreadObservation


def _fake_fetch_obs() -> FetchThreadObservation:
    """Return a minimal FetchThreadObservation for testing."""
    return FetchThreadObservation(
        root_post={"author_id": "u1", "message": "hello", "created_at": "2024-01-01"},
        replies=[],
        channel_id="chan1",
        channel_name="general",
        total_replies=0,
    )


def _make_config(max_reference_depth: int | None = None) -> MattermostSummarizerConfig:
    return MattermostSummarizerConfig(
        mattermost_url=HttpUrl("https://chat.example.com"),
        mattermost_token=SecretStr("tok"),
        llm_api_key=SecretStr("key"),
        max_reference_depth=max_reference_depth,
        critic_enabled=False,
    )


class TestEffectiveDepthDefaults:
    """When max_reference_depth is not explicitly configured (None), depth is inferred from level."""

    @pytest.mark.parametrize(
        "level,expected_depth",
        [
            (SummaryLevel.BRIEF, 0),
            (SummaryLevel.NORMAL, 1),
            (SummaryLevel.DETAILED, 3),
        ],
    )
    def test_depth_inferred_from_level(self, level: SummaryLevel, expected_depth: int) -> None:
        config = _make_config(max_reference_depth=None)
        summarizer = MattermostSummarizer(config)

        captured: list[int] = []

        original_tracker = __import__(
            "mattermost_summarizer.tools.reference_tracker",
            fromlist=["ReferenceTracker"],
        ).ReferenceTracker

        class CapturingTracker(original_tracker):  # type: ignore[misc]
            def __init__(self, max_depth: int = 3) -> None:
                super().__init__(max_depth=max_depth)
                captured.append(max_depth)

        with (
            patch("mattermost_summarizer.summarizer.ReferenceTracker", CapturingTracker),
            patch("mattermost_summarizer.summarizer.MattermostClient") as mock_client_cls,
            patch("mattermost_summarizer.summarizer.FetchThreadExecutor") as mock_executor_cls,
            patch("mattermost_summarizer.summarizer.register_subagents"),
            patch("mattermost_summarizer.summarizer.build_orchestrator_agent"),
            patch("mattermost_summarizer.summarizer.LocalConversation") as mock_conv_cls,
            patch("mattermost_summarizer.summarizer.parse_permalink", return_value="post123"),
            patch("mattermost_summarizer.summarizer.FileConversationVisualizer"),
        ):
            # Wire up a mock conversation that immediately triggers finish
            mock_conv = MagicMock()
            mock_conv_cls.return_value.__enter__ = MagicMock(return_value=mock_conv)
            mock_conv_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_conv_cls.return_value = mock_conv
            mock_conv.state.events = []

            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            mock_executor_cls.return_value.return_value = _fake_fetch_obs()

            # Make the conversation run loop short-circuit by raising on run()
            mock_conv.run.side_effect = RuntimeError("stop")

            try:
                summarizer.summarize("https://chat.example.com/team/pl/post123", level=level)
            except Exception:
                pass  # We only care about side effects (captured depths)

        assert len(captured) == 1, "ReferenceTracker should be instantiated once"
        assert captured[0] == expected_depth, f"Expected depth {expected_depth} for level {level}, got {captured[0]}"


class TestEffectiveDepthExplicitConfig:
    """When max_reference_depth is explicitly configured, it always wins over the level default."""

    @pytest.mark.parametrize("level", [SummaryLevel.BRIEF, SummaryLevel.NORMAL, SummaryLevel.DETAILED])
    def test_explicit_depth_overrides_level(self, level: SummaryLevel) -> None:
        explicit_depth = 5
        config = _make_config(max_reference_depth=explicit_depth)
        summarizer = MattermostSummarizer(config)

        captured: list[int] = []

        original_tracker = __import__(
            "mattermost_summarizer.tools.reference_tracker",
            fromlist=["ReferenceTracker"],
        ).ReferenceTracker

        class CapturingTracker(original_tracker):  # type: ignore[misc]
            def __init__(self, max_depth: int = 3) -> None:
                super().__init__(max_depth=max_depth)
                captured.append(max_depth)

        with (
            patch("mattermost_summarizer.summarizer.ReferenceTracker", CapturingTracker),
            patch("mattermost_summarizer.summarizer.MattermostClient") as mock_client_cls,
            patch("mattermost_summarizer.summarizer.FetchThreadExecutor") as mock_executor_cls,
            patch("mattermost_summarizer.summarizer.register_subagents"),
            patch("mattermost_summarizer.summarizer.build_orchestrator_agent"),
            patch("mattermost_summarizer.summarizer.LocalConversation") as mock_conv_cls,
            patch("mattermost_summarizer.summarizer.parse_permalink", return_value="post123"),
            patch("mattermost_summarizer.summarizer.FileConversationVisualizer"),
        ):
            mock_conv = MagicMock()
            mock_conv_cls.return_value = mock_conv
            mock_conv.state.events = []
            mock_conv.run.side_effect = RuntimeError("stop")

            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            mock_executor_cls.return_value.return_value = _fake_fetch_obs()

            try:
                summarizer.summarize("https://chat.example.com/team/pl/post123", level=level)
            except Exception:
                pass

        assert len(captured) == 1
        assert captured[0] == explicit_depth, (
            f"Expected explicit depth {explicit_depth} to win over level {level}, got {captured[0]}"
        )

    def test_explicit_depth_zero_wins_over_detailed(self) -> None:
        """An explicit depth=0 beats the detailed level's default of 3."""
        config = _make_config(max_reference_depth=0)
        summarizer = MattermostSummarizer(config)

        captured: list[int] = []

        original_tracker = __import__(
            "mattermost_summarizer.tools.reference_tracker",
            fromlist=["ReferenceTracker"],
        ).ReferenceTracker

        class CapturingTracker(original_tracker):  # type: ignore[misc]
            def __init__(self, max_depth: int = 3) -> None:
                super().__init__(max_depth=max_depth)
                captured.append(max_depth)

        with (
            patch("mattermost_summarizer.summarizer.ReferenceTracker", CapturingTracker),
            patch("mattermost_summarizer.summarizer.MattermostClient") as mock_client_cls,
            patch("mattermost_summarizer.summarizer.FetchThreadExecutor") as mock_executor_cls,
            patch("mattermost_summarizer.summarizer.register_subagents"),
            patch("mattermost_summarizer.summarizer.build_orchestrator_agent"),
            patch("mattermost_summarizer.summarizer.LocalConversation") as mock_conv_cls,
            patch("mattermost_summarizer.summarizer.parse_permalink", return_value="post123"),
            patch("mattermost_summarizer.summarizer.FileConversationVisualizer"),
        ):
            mock_conv = MagicMock()
            mock_conv_cls.return_value = mock_conv
            mock_conv.state.events = []
            mock_conv.run.side_effect = RuntimeError("stop")

            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            mock_executor_cls.return_value.return_value = _fake_fetch_obs()

            try:
                summarizer.summarize("https://chat.example.com/team/pl/post123", level=SummaryLevel.DETAILED)
            except Exception:
                pass

        assert len(captured) == 1
        assert captured[0] == 0
