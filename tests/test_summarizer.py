"""Tests for summarizer.py - _on_finish_callback and _extract_finish_action."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from mattermost_summarizer.levels import (
    BriefFinishAction,
    DetailedFinishAction,
    NormalFinishAction,
    SummarizerFinishActionBase,
)
from mattermost_summarizer.summarizer import (
    _extract_finish_action,
)


class MockEvent:
    def __init__(self, action: Any | None = None, observation: Any | None = None) -> None:
        self.action: Any | None = action
        self.observation: Any | None = observation


class MockConversationState:
    def __init__(self, events: list[MockEvent]) -> None:
        self._events: list[MockEvent] = events

    @property
    def events(self) -> list[MockEvent]:
        return self._events


class MockConversation:
    def __init__(self, events: list[MockEvent], stuck_detector: Any | None = None) -> None:
        self.state: MockConversationState = MockConversationState(events)
        self._paused: bool = False
        self._stuck_detector: Any | None = stuck_detector

    @property
    def stuck_detector(self) -> Any | None:
        return self._stuck_detector

    def pause(self) -> None:
        self._paused = True


class MockStuckDetector:
    def __init__(self, is_stuck_value: bool = False) -> None:
        self._is_stuck: bool = is_stuck_value

    def is_stuck(self) -> bool:
        return self._is_stuck


class TestOnFinishCallback:
    """Tests for the _on_finish_callback closure inside summarize()."""

    def _build_callback(self):
        conv_ref: list[MockConversation | None] = [None]
        finish_seen_ref: list[bool] = [False]

        def _on_finish_callback(event: MockEvent) -> None:
            if (
                not finish_seen_ref[0]
                and hasattr(event, "action")
                and isinstance(getattr(event, "action", None), SummarizerFinishActionBase)
                and conv_ref[0] is not None
            ):
                finish_seen_ref[0] = True
                conv_ref[0].pause()

        return _on_finish_callback, conv_ref, finish_seen_ref

    def test_callback_triggers_on_brief_finish_action(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        event = MockEvent(action=BriefFinishAction(tldr="- Point", action_items=[]))
        callback(event)

        assert conv._paused is True

    def test_callback_triggers_on_normal_finish_action(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        event = MockEvent(
            action=NormalFinishAction(
                tldr="- Point",
                narrative="Story",
                action_items=[],
                participants=[],
            )
        )
        callback(event)

        assert conv._paused is True

    def test_callback_triggers_on_detailed_finish_action(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        event = MockEvent(
            action=DetailedFinishAction(
                tldr="- Point",
                narrative="Story",
                action_items=[],
                participants=[],
                open_questions=[],
                context_sources=[],
            )
        )
        callback(event)

        assert conv._paused is True

    def test_callback_ignores_non_finish_action(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        class SomeOtherAction:
            pass

        event = MockEvent(action=SomeOtherAction())
        callback(event)

        assert conv._paused is False

    def test_callback_ignores_event_with_no_action(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        event = MockEvent(action=None)
        callback(event)

        assert conv._paused is False

    def test_callback_only_pauses_once(self) -> None:
        callback, conv_ref, finish_seen_ref = self._build_callback()
        conv = MockConversation([])
        conv_ref[0] = conv

        event1 = MockEvent(action=BriefFinishAction(tldr="- First", action_items=[]))
        callback(event1)
        assert conv._paused is True
        assert finish_seen_ref[0] is True

        conv._paused = False
        event2 = MockEvent(
            action=NormalFinishAction(
                tldr="- Second",
                narrative="Story",
                action_items=[],
                participants=[],
            )
        )
        callback(event2)
        assert conv._paused is False

    def test_callback_does_nothing_when_conv_not_set(self) -> None:
        callback, conv_ref, _ = self._build_callback()
        conv_ref[0] = None

        event = MockEvent(action=BriefFinishAction(tldr="- Point", action_items=[]))
        callback(event)


class TestExtractFinishAction:
    """Tests for _extract_finish_action()."""

    def test_extract_returns_none_when_no_events(self) -> None:
        conv = MockConversation([])
        result = _extract_finish_action(conv)
        assert result is None

    def test_extract_returns_none_when_no_state(self) -> None:
        conv = MagicMock(spec=[])
        conv.state = None
        result = _extract_finish_action(conv)
        assert result is None

    def test_extract_finds_brief_finish_action(self) -> None:
        action = BriefFinishAction(tldr="- Point", action_items=[])
        events = [MockEvent(action=action)]
        conv = MockConversation(events)

        result = _extract_finish_action(conv)
        assert result is action

    def test_extract_finds_normal_finish_action(self) -> None:
        action = NormalFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
        )
        events = [MockEvent(action=action)]
        conv = MockConversation(events)

        result = _extract_finish_action(conv)
        assert result is action

    def test_extract_finds_detailed_finish_action(self) -> None:
        action = DetailedFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=[],
            context_sources=[],
        )
        events = [MockEvent(action=action)]
        conv = MockConversation(events)

        result = _extract_finish_action(conv)
        assert result is action

    def test_extract_returns_last_finish_action_in_reverse_order(self) -> None:
        action1 = BriefFinishAction(tldr="- First", action_items=[])
        action2 = NormalFinishAction(
            tldr="- Second",
            narrative="Story",
            action_items=[],
            participants=[],
        )
        events = [MockEvent(action=action1), MockEvent(action=action2)]
        conv = MockConversation(events)

        result = _extract_finish_action(conv)
        assert result is action2

    def test_extract_skips_non_finish_actions(self) -> None:
        class SomeOtherAction:
            pass

        action = NormalFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
        )
        events = [
            MockEvent(action=SomeOtherAction()),
            MockEvent(action=SomeOtherAction()),
            MockEvent(action=action),
        ]
        conv = MockConversation(events)

        result = _extract_finish_action(conv)
        assert result is action

    def test_extract_returns_none_for_empty_events(self) -> None:
        conv = MockConversation([])
        result = _extract_finish_action(conv)
        assert result is None


class TestSummarizerFinishActionBaseIsinstance:
    """Verify that all level actions are instances of SummarizerFinishActionBase."""

    def test_brief_finish_action_isinstance(self) -> None:
        action = BriefFinishAction(tldr="- Point", action_items=[])
        assert isinstance(action, SummarizerFinishActionBase)

    def test_normal_finish_action_isinstance(self) -> None:
        action = NormalFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
        )
        assert isinstance(action, SummarizerFinishActionBase)

    def test_detailed_finish_action_isinstance(self) -> None:
        action = DetailedFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=[],
            context_sources=[],
        )
        assert isinstance(action, SummarizerFinishActionBase)

    def test_is_summarizer_finish_sentinel(self) -> None:
        action = BriefFinishAction(tldr="- Point", action_items=[])
        assert action.is_summarizer_finish is True

        action2 = DetailedFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=[],
            context_sources=[],
        )
        assert action2.is_summarizer_finish is True


class TestSummarizerPromptAndChatWindow:
    def test_custom_prompt_is_appended_and_channel_window_is_used(self) -> None:
        from datetime import datetime

        from pydantic import HttpUrl, SecretStr

        from mattermost_summarizer.config import MattermostSummarizerConfig
        from mattermost_summarizer.models import Channel, PostData
        from mattermost_summarizer.summarizer import MattermostSummarizer

        config = MattermostSummarizerConfig(
            mattermost_url=HttpUrl("https://chat.example.com"),
            mattermost_token=SecretStr("tok"),
            llm_api_key=SecretStr("key"),
            critic_enabled=False,
        )
        summarizer = MattermostSummarizer(config)

        mock_conv = MagicMock()
        mock_conv.state.events = []
        mock_conv.run.side_effect = RuntimeError("stop")

        mock_client = MagicMock()
        mock_client.get_team_id_by_name.return_value = "team1"
        mock_client.get_channel_by_name.return_value = Channel(
            id="channel1",
            name="general",
            display_name="General",
            team_name="canonical",
        )
        mock_client.get_channel_posts.return_value = [
            PostData(
                id="post1",
                author_id="user1",
                message="First message",
                created_at=datetime(2026, 6, 26, 10, 0, 0),
                root_id="",
            ),
            PostData(
                id="post2",
                author_id="user2",
                message="Second message",
                created_at=datetime(2026, 6, 26, 10, 5, 0),
                root_id="post1",
            ),
        ]
        mock_client.get_user.side_effect = lambda user_id: MagicMock(
            username={"user1": "alice", "user2": "bob"}[user_id]
        )

        with (
            patch("mattermost_summarizer.summarizer.MattermostClient") as mock_client_cls,
            patch("mattermost_summarizer.summarizer.register_subagents"),
            patch("mattermost_summarizer.summarizer.build_orchestrator_agent"),
            patch("mattermost_summarizer.summarizer.LocalConversation") as mock_conv_cls,
            patch("mattermost_summarizer.summarizer.parse_channel_url", return_value=("canonical", "general")),
            patch("mattermost_summarizer.summarizer.FileConversationVisualizer"),
        ):
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_conv_cls.return_value = mock_conv

            try:
                summarizer.summarize(
                    "https://chat.example.com/canonical/channels/general",
                    prompt="Focus on decisions.",
                    start_time="2026-06-26T09:00:00",
                    end_time="2026-06-26T11:00:00",
                )
            except Exception:
                pass

        sent_message = mock_conv.send_message.call_args.args[0]
        assert "Focus on decisions." in sent_message
        assert "Summarize this Mattermost chat window for channel #general." in sent_message
        assert "First message" in sent_message
        assert "Second message" in sent_message


# ---------------------------------------------------------------------------
# Helpers shared by the pause-callback and extract-delegate tests
# ---------------------------------------------------------------------------


class _FakeDelegateObservation:
    """Minimal stand-in for DelegateObservation."""

    def __init__(self, command: str, content_text: str = "") -> None:
        self.command = command
        self._text = content_text

    @property
    def to_llm_content(self) -> list[Any]:
        class _TextContent:
            def __init__(self, text: str) -> None:
                self.text = text

        return [_TextContent(self._text)] if self._text else []


class _FakeObservationEvent:
    """Minimal stand-in for ObservationEvent with a DelegateObservation."""

    def __init__(self, observation: Any) -> None:
        self.observation = observation


class _FakeOtherObservation:
    """Any non-DelegateObservation."""

    pass


class _FakeActionEvent:
    """Event with an action attribute but no observation."""

    def __init__(self, action: Any = None) -> None:
        self.action = action
