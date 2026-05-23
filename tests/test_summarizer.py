"""Tests for summarizer.py - _on_finish_callback and _extract_finish_action."""

from __future__ import annotations

from typing import Any

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
        from unittest.mock import MagicMock

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
