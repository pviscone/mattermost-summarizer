"""Tests for summarization levels package."""

from io import StringIO

from rich.console import Console

from mattermost_summarizer.levels import (
    BRIEF_ADDENDUM,
    DETAILED_ADDENDUM,
    NORMAL_ADDENDUM,
    AnySummaryResult,
    BriefSummaryResult,
    DetailedSummaryResult,
    NormalSummaryResult,
    SummaryLevel,
    SummaryMeta,
)


class TestSummaryLevel:
    def test_summary_level_values(self) -> None:
        assert SummaryLevel.BRIEF.value == "brief"
        assert SummaryLevel.NORMAL.value == "normal"
        assert SummaryLevel.DETAILED.value == "detailed"

    def test_summary_level_default(self) -> None:
        assert SummaryLevel.NORMAL is not None


class TestBriefSummaryResult:
    def test_create_brief_summary_result(self) -> None:
        result = BriefSummaryResult(
            tldr="- Item 1\n- Item 2",
            action_items=["Action 1", "Action 2"],
            metadata=SummaryMeta(
                thread_length=10,
                cost=0.05,
                model_used="openai/gpt-4o",
                duration_seconds=3.5,
            ),
        )
        assert "Item 1" in result.tldr
        assert result.level == "brief"
        assert result.action_items == ["Action 1", "Action 2"]

    def test_brief_summary_no_narrative(self) -> None:
        result = BriefSummaryResult(
            tldr="- Key point",
            action_items=[],
        )
        assert not hasattr(result, "narrative")

    def test_brief_summary_str_format(self) -> None:
        result = BriefSummaryResult(
            tldr="- Key point",
            action_items=["Action 1"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        output = str(result)
        assert "TL;DR" in output
        assert "ACTION ITEMS" in output
        assert "METADATA" in output

    def test_brief_summary_render_rich(self) -> None:
        result = BriefSummaryResult(
            tldr="- Key point",
            action_items=["Action 1"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        result.render_rich(console)
        output = buffer.getvalue()
        assert "TL;DR" in output
        assert "ACTION ITEMS" in output
        assert "Key point" in output


class TestNormalSummaryResult:
    def test_create_normal_summary_result(self) -> None:
        result = NormalSummaryResult(
            tldr="- Item 1\n- Item 2",
            key_findings=["Finding one"],
            narrative="Once upon a time...",
            action_items=["Action 1"],
            participants=["Alice", "Bob"],
            metadata=SummaryMeta(
                thread_length=10,
                cost=0.05,
                model_used="openai/gpt-4o",
                duration_seconds=3.5,
            ),
        )
        assert "Item 1" in result.tldr
        assert "Alice" in result.participants
        assert result.level == "normal"
        assert result.metadata.thread_length == 10

    def test_normal_summary_str_format(self) -> None:
        result = NormalSummaryResult(
            tldr="- Key point",
            narrative="The story goes...",
            action_items=["Action 1"],
            participants=["Alice"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        output = str(result)
        assert "TL;DR" in output
        assert "NARRATIVE" in output
        assert "ACTION ITEMS" in output
        assert "PARTICIPANTS" in output
        assert "METADATA" in output

    def test_normal_summary_render_rich(self) -> None:
        result = NormalSummaryResult(
            tldr="- Key point",
            key_findings=["Finding one"],
            narrative="The story goes...",
            action_items=["Action 1"],
            participants=["Alice"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        result.render_rich(console)
        output = buffer.getvalue()
        assert "TL;DR" in output
        assert "NARRATIVE" in output
        assert "KEY FINDINGS" in output
        assert "ACTION ITEMS" in output
        assert "PARTICIPANTS" in output


class TestDetailedSummaryResult:
    def test_create_detailed_summary_result(self) -> None:
        result = DetailedSummaryResult(
            tldr="- Item 1\n- Item 2",
            key_findings=["Finding one"],
            narrative="Once upon a time...",
            action_items=["Action 1"],
            participants=["Alice", "Bob"],
            open_questions=["What about X?"],
            context_sources=["https://example.com/doc"],
            metadata=SummaryMeta(
                thread_length=10,
                cost=0.05,
                model_used="openai/gpt-4o",
                duration_seconds=3.5,
            ),
        )
        assert "Item 1" in result.tldr
        assert "Alice" in result.participants
        assert result.level == "detailed"
        assert result.open_questions == ["What about X?"]
        assert result.context_sources == ["https://example.com/doc"]

    def test_detailed_summary_str_format(self) -> None:
        result = DetailedSummaryResult(
            tldr="- Key point",
            narrative="The story goes...",
            action_items=["Action 1"],
            participants=["Alice"],
            open_questions=["What about X?"],
            context_sources=["https://example.com/doc"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        output = str(result)
        assert "TL;DR" in output
        assert "NARRATIVE" in output
        assert "OPEN QUESTIONS" in output
        assert "CONTEXT SOURCES" in output

    def test_detailed_summary_render_rich(self) -> None:
        result = DetailedSummaryResult(
            tldr="- Key point",
            narrative="The story goes...",
            action_items=["Action 1"],
            participants=["Alice"],
            open_questions=["What about X?"],
            context_sources=["https://example.com/doc"],
            metadata=SummaryMeta(
                thread_length=5,
                cost=0.02,
                model_used="test-model",
                duration_seconds=1.0,
            ),
        )
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        result.render_rich(console)
        output = buffer.getvalue()
        assert "TL;DR" in output
        assert "NARRATIVE" in output
        assert "OPEN QUESTIONS" in output
        assert "CONTEXT SOURCES" in output
        assert "What about X?" in output
        assert "https://example.com/doc" in output


class TestPromptAddendums:
    def test_brief_addendum_non_empty(self) -> None:
        assert BRIEF_ADDENDUM is not None
        assert len(BRIEF_ADDENDUM) > 0
        assert "BRIEF" in BRIEF_ADDENDUM

    def test_normal_addendum_non_empty(self) -> None:
        assert NORMAL_ADDENDUM is not None
        assert len(NORMAL_ADDENDUM) > 0
        assert "NORMAL" in NORMAL_ADDENDUM

    def test_detailed_addendum_non_empty(self) -> None:
        assert DETAILED_ADDENDUM is not None
        assert len(DETAILED_ADDENDUM) > 0
        assert "DETAILED" in DETAILED_ADDENDUM

    def test_addendums_are_distinct(self) -> None:
        assert BRIEF_ADDENDUM != NORMAL_ADDENDUM
        assert NORMAL_ADDENDUM != DETAILED_ADDENDUM
        assert BRIEF_ADDENDUM != DETAILED_ADDENDUM


class TestLevelSchemas:
    def test_brief_finish_action_no_narrative(self) -> None:
        from mattermost_summarizer.levels.brief import BriefFinishAction

        action = BriefFinishAction(tldr="- Point", action_items=[])
        assert hasattr(action, "tldr")
        assert (
            not hasattr(action, "narrative")
            or getattr(action.__class__.model_fields.get("narrative"), "required", True) is False
        )

    def test_detailed_finish_action_has_extra_fields(self) -> None:
        from mattermost_summarizer.levels.detailed import DetailedFinishAction

        action = DetailedFinishAction(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=["Q1"],
            context_sources=["URL"],
        )
        assert hasattr(action, "open_questions")
        assert hasattr(action, "context_sources")


class TestJSONOutput:
    def test_brief_json_has_level_field(self) -> None:
        result = BriefSummaryResult(tldr="- Point", action_items=[])
        json_str = result.model_dump_json()
        assert '"level"' in json_str and '"brief"' in json_str

    def test_normal_json_has_level_field(self) -> None:
        result = NormalSummaryResult(
            tldr="- Point",
            narrative="Story",
        )
        json_str = result.model_dump_json()
        assert '"level"' in json_str and '"normal"' in json_str

    def test_detailed_json_has_level_field(self) -> None:
        result = DetailedSummaryResult(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=[],
            context_sources=[],
        )
        json_str = result.model_dump_json()
        assert '"level"' in json_str and '"detailed"' in json_str

    def test_brief_json_no_narrative_key(self) -> None:
        result = BriefSummaryResult(tldr="- Point", action_items=[])
        json_str = result.model_dump_json()
        assert "narrative" not in json_str

    def test_detailed_json_has_open_questions(self) -> None:
        result = DetailedSummaryResult(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=["What about X?"],
            context_sources=[],
        )
        json_str = result.model_dump_json()
        assert "open_questions" in json_str
        assert "What about X?" in json_str


class TestAnySummaryResult:
    def test_any_summary_result_union(self) -> None:
        brief = BriefSummaryResult(tldr="- Point", action_items=[])
        normal = NormalSummaryResult(tldr="- Point", narrative="Story")
        detailed = DetailedSummaryResult(
            tldr="- Point",
            narrative="Story",
            action_items=[],
            participants=[],
            open_questions=[],
            context_sources=[],
        )

        results: list[AnySummaryResult] = [brief, normal, detailed]
        assert all(r.level in ("brief", "normal", "detailed") for r in results)


class TestToolSchemas:
    def test_brief_finish_tool_has_tldr_field(self) -> None:
        from mattermost_summarizer.levels import BriefFinishTool

        tool = BriefFinishTool.create()[0]
        fields = list(tool.action_type.model_fields.keys())
        assert "tldr" in fields, f"BriefFinishTool should have 'tldr' field, got {fields}"
        assert "narrative" not in fields

    def test_normal_finish_tool_has_narrative_field(self) -> None:
        from mattermost_summarizer.levels import NormalFinishTool

        tool = NormalFinishTool.create()[0]
        fields = list(tool.action_type.model_fields.keys())
        assert "narrative" in fields, f"NormalFinishTool should have 'narrative' field, got {fields}"

    def test_detailed_finish_tool_has_open_questions_field(self) -> None:
        from mattermost_summarizer.levels import DetailedFinishTool

        tool = DetailedFinishTool.create()[0]
        fields = list(tool.action_type.model_fields.keys())
        assert "open_questions" in fields, f"DetailedFinishTool should have 'open_questions' field, got {fields}"
        assert "context_sources" in fields
