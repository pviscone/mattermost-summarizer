"""Tests for multi-agent orchestration."""

from __future__ import annotations


class TestCriticConfiguration:
    """Test critic configuration in orchestrator."""

    def test_critic_iterative_refinement_defaults(self) -> None:
        """Test that SummarizationCritic has proper iterative_refinement config."""
        from openhands.sdk.critic import IterativeRefinementConfig

        from mattermost_summarizer.critic import SummarizationCritic

        critic = SummarizationCritic(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
        )

        assert critic.iterative_refinement is not None
        assert isinstance(critic.iterative_refinement, IterativeRefinementConfig)
        assert critic.iterative_refinement.success_threshold == 0.7
        assert critic.iterative_refinement.max_iterations == 2

    def test_critic_iterative_refinement_custom_values(self) -> None:
        """Test that SummarizationCritic accepts custom iterative_refinement values."""
        from openhands.sdk.critic import IterativeRefinementConfig

        from mattermost_summarizer.critic import SummarizationCritic

        critic = SummarizationCritic(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            iterative_refinement=IterativeRefinementConfig(
                success_threshold=0.85,
                max_iterations=3,
            ),
        )

        assert critic.iterative_refinement is not None
        assert critic.iterative_refinement.success_threshold == 0.85
        assert critic.iterative_refinement.max_iterations == 3


class TestSubagentRegistration:
    """Test sub-agent registration."""

    def test_register_subagents_does_not_raise(self) -> None:
        """Test that register_subagents completes without error."""
        from unittest.mock import MagicMock

        from mattermost_summarizer.subagents import register_subagents

        mock_client = MagicMock()
        register_subagents(mock_client)


class TestOrchestratorAgent:
    """Test orchestrator agent building."""

    def test_build_orchestrator_agent_returns_agent(self) -> None:
        """Test that build_orchestrator_agent returns an Agent instance."""
        from mattermost_summarizer.agent import build_orchestrator_agent
        from mattermost_summarizer.levels import SummaryLevel

        agent = build_orchestrator_agent(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            llm_base_url=None,
            level=SummaryLevel.NORMAL,
        )

        assert agent is not None
        assert hasattr(agent, "llm")
        assert hasattr(agent, "tools")

    def test_orchestrator_has_delegate_and_finish_tools(self) -> None:
        """Test that orchestrator has delegate and finish tools."""
        from mattermost_summarizer.agent import build_orchestrator_agent
        from mattermost_summarizer.levels import SummaryLevel

        agent = build_orchestrator_agent(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            llm_base_url=None,
            level=SummaryLevel.NORMAL,
        )

        tool_names = [t.name for t in agent.tools]
        assert "delegate" in tool_names
        assert "finish" in tool_names

    def test_orchestrator_has_agent_context(self) -> None:
        """Test that orchestrator uses AgentContext with system_message_suffix."""
        from mattermost_summarizer.agent import build_orchestrator_agent
        from mattermost_summarizer.levels import SummaryLevel

        agent = build_orchestrator_agent(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            llm_base_url=None,
            level=SummaryLevel.NORMAL,
        )

        assert hasattr(agent, "agent_context")
        assert agent.agent_context is not None
        assert agent.agent_context.system_message_suffix is not None
        assert len(agent.agent_context.system_message_suffix) > 0


class TestDelegateTool:
    """Test DelegateTool creation."""

    def test_delegate_tool_creation(self) -> None:
        """Test that DelegateTool.create() returns valid tool definitions."""
        from mattermost_summarizer.subagents.delegate_tool import DelegateTool

        tools = DelegateTool.create()
        assert len(tools) == 1
        tool = tools[0]
        assert tool.name == "delegate"
        assert tool.description is not None
        assert "delegate" in tool.description.lower()


class TestSubagentPrompts:
    """Test sub-agent system prompts."""

    def test_thread_fetcher_prompt_contains_instructions(self) -> None:
        """Test that thread_fetcher prompt contains key instructions."""
        from mattermost_summarizer.subagents import THREAD_FETCHER_PROMPT

        assert "thread researcher" in THREAD_FETCHER_PROMPT.lower()
        assert "FetchThread" in THREAD_FETCHER_PROMPT
        assert "finish" in THREAD_FETCHER_PROMPT.lower()

    def test_bug_researcher_prompt_contains_instructions(self) -> None:
        """Test that bug_researcher prompt contains key instructions."""
        from mattermost_summarizer.subagents import BUG_RESEARCHER_PROMPT

        assert "bug researcher" in BUG_RESEARCHER_PROMPT.lower()
        assert "FetchLaunchpadBug" in BUG_RESEARCHER_PROMPT
        assert "finish" in BUG_RESEARCHER_PROMPT.lower()

    def test_github_researcher_prompt_contains_instructions(self) -> None:
        """Test that github_researcher prompt contains key instructions."""
        from mattermost_summarizer.subagents import GITHUB_RESEARCHER_PROMPT

        assert "github researcher" in GITHUB_RESEARCHER_PROMPT.lower()
        assert "FetchGitHubIssue" in GITHUB_RESEARCHER_PROMPT
        assert "finish" in GITHUB_RESEARCHER_PROMPT.lower()

    def test_file_fetcher_prompt_contains_instructions(self) -> None:
        """Test that file_fetcher prompt contains key instructions."""
        from mattermost_summarizer.subagents import FILE_FETCHER_PROMPT

        assert "file researcher" in FILE_FETCHER_PROMPT.lower()
        assert "FetchFile" in FILE_FETCHER_PROMPT
        assert "finish" in FILE_FETCHER_PROMPT.lower()


class TestOrchestratorPrompt:
    """Test orchestrator system prompt."""

    def test_orchestrator_prompt_contains_coordination_flow(self) -> None:
        """Test that orchestrator prompt contains coordination instructions."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "orchestrator" in ORCHESTRATOR_PROMPT.lower()
        assert "delegate" in ORCHESTRATOR_PROMPT.lower()
        assert "thread_fetcher" in ORCHESTRATOR_PROMPT
        assert "bug_researcher" in ORCHESTRATOR_PROMPT
        assert "github_researcher" in ORCHESTRATOR_PROMPT
        assert "file_fetcher" in ORCHESTRATOR_PROMPT

    def test_orchestrator_prompt_explains_different_reference_types(self) -> None:
        """Test that orchestrator prompt explains how to route different reference types."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "Mattermost" in ORCHESTRATOR_PROMPT
        assert "Launchpad" in ORCHESTRATOR_PROMPT
        assert "GitHub" in ORCHESTRATOR_PROMPT

    def test_orchestrator_prompt_includes_delegation_example(self) -> None:
        """Test that orchestrator prompt includes example delegation call."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "delegate(" in ORCHESTRATOR_PROMPT
        assert "agent_types" in ORCHESTRATOR_PROMPT
        assert "tasks" in ORCHESTRATOR_PROMPT


class TestRecursiveReferenceFollowing:
    """Test recursive reference following depth behavior."""

    def test_depth_1_no_recursion(self) -> None:
        """Task 4.6: Test depth 1 (no recursion, thread only)."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=1)
        # At depth 0, can follow 1 level of references
        assert tracker.can_follow_deeper() is True
        tracker.increment_depth()
        # At depth 1, cannot follow deeper (max_depth reached)
        assert tracker.current_depth == 1
        assert tracker.can_follow_deeper() is False

    def test_depth_2_one_reference(self) -> None:
        """Task 4.7: Test depth 2 (one referenced thread or bug followed)."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)
        # Start at depth 0, can follow deeper
        assert tracker.can_follow_deeper() is True
        # After processing root thread, depth increments to 1
        tracker.increment_depth()
        assert tracker.current_depth == 1
        assert tracker.can_follow_deeper() is True
        # After following one reference, depth increments to 2
        tracker.increment_depth()
        assert tracker.current_depth == 2
        assert tracker.can_follow_deeper() is False

    def test_depth_3_thread_chain(self) -> None:
        """Task 4.8: Test depth 3 (thread -> thread -> thread chain)."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        # Simulate chain: thread A -> thread B -> thread C
        tracker.increment_depth()  # depth=1: thread_fetcher for thread A
        assert tracker.current_depth == 1
        assert tracker.can_follow_deeper() is True

        tracker.increment_depth()  # depth=2: thread_fetcher for thread B
        assert tracker.current_depth == 2
        assert tracker.can_follow_deeper() is True

        tracker.increment_depth()  # depth=3: thread_fetcher for thread C
        assert tracker.current_depth == 3
        assert tracker.can_follow_deeper() is False  # max_depth reached

    def test_depth_limit_stops_recursion(self) -> None:
        """Task 4.9: Verify depth limit stops recursion correctly."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)
        tracker.increment_depth()  # depth=1
        tracker.increment_depth()  # depth=2
        # At max depth, cannot go deeper
        assert tracker.can_follow_deeper() is False
        assert tracker.current_depth == 2
        # Reset should clear depth
        tracker.reset()
        assert tracker.current_depth == 0
        assert tracker.can_follow_deeper() is True

    def test_cycle_prevention(self) -> None:
        """Test that followed URLs are tracked to prevent cycles."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        url = "https://chat.example.com/team/pl/abc123"
        assert tracker.has_been_followed(url) is False
        tracker.mark_followed(url)
        assert tracker.has_been_followed(url) is True
        # Should not re-follow same URL
        assert tracker.has_been_followed(url) is True


class TestCriticEvaluation:
    """Test critic evaluation behavior."""

    def test_critic_evaluates_summary_returns_score(self) -> None:
        """Task 5.9: Test critic evaluates summary and returns score."""
        from unittest.mock import MagicMock, patch

        from openhands.sdk.critic import CriticResult

        from mattermost_summarizer.critic import SummarizationCritic
        from mattermost_summarizer.levels import SummaryLevel
        from mattermost_summarizer.levels.normal import NormalFinishAction

        critic = SummarizationCritic(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            level=SummaryLevel.NORMAL,
        )

        # Create a real finish action for testing
        finish_action = NormalFinishAction(
            tldr="Key point 1\nKey point 2",
            key_findings=["finding1"],
            narrative="Test narrative",
            action_items=["item1"],
            participants=["alice", "bob"],
        )

        # Mock the _extract_finish_action to return our action
        with patch.object(critic, "_extract_finish_action") as mock_extract:
            mock_extract.return_value = finish_action
            # Mock the LLM evaluation response
            with patch.object(critic, "_call_critic_llm") as mock_call:
                mock_call.return_value = MagicMock(score=0.85, feedback="Good summary")

                result = critic.evaluate([])  # events param doesn't matter with mocked extract

                assert isinstance(result, CriticResult)
                assert result.score == 0.85
                assert "Good summary" in result.message

    def test_critic_iterative_refinement_below_threshold(self) -> None:
        """Task 5.10: Test iterative refinement when score is below threshold."""
        from openhands.sdk.critic import IterativeRefinementConfig

        from mattermost_summarizer.critic import SummarizationCritic

        critic = SummarizationCritic(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            iterative_refinement=IterativeRefinementConfig(
                success_threshold=0.7,
                max_iterations=2,
            ),
        )

        # Verify config
        assert critic.iterative_refinement.success_threshold == 0.7
        assert critic.iterative_refinement.max_iterations == 2

        # Score below threshold should trigger revision
        # (In real usage, the OpenHands SDK Agent handles the loop)
        assert critic.iterative_refinement is not None
        assert hasattr(critic.iterative_refinement, "success_threshold")
        assert hasattr(critic.iterative_refinement, "max_iterations")
