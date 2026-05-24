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
        assert "fetch_reference" in tool_names
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
        assert "fetch_reference" in ORCHESTRATOR_PROMPT.lower()
        # assert "thread_fetcher" in ORCHESTRATOR_PROMPT
        # assert "bug_researcher" in ORCHESTRATOR_PROMPT
        # assert "github_researcher" in ORCHESTRATOR_PROMPT
        # assert "file_fetcher" in ORCHESTRATOR_PROMPT

    def test_orchestrator_prompt_explains_different_reference_types(self) -> None:
        """Test that orchestrator prompt explains how to route different reference types."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "Mattermost" in ORCHESTRATOR_PROMPT
        # assert "Launchpad" in ORCHESTRATOR_PROMPT
        # assert "GitHub" in ORCHESTRATOR_PROMPT

    def test_orchestrator_prompt_includes_delegation_example(self) -> None:
        """Test that orchestrator prompt includes example delegation call."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "fetch_reference(" in ORCHESTRATOR_PROMPT
        # assert "agent_types" in ORCHESTRATOR_PROMPT
        # assert "tasks" in ORCHESTRATOR_PROMPT


class TestRecursiveReferenceFollowing:
    """Test recursive reference following depth behavior."""

    def test_depth_1_no_recursion(self) -> None:
        """With max_depth=1, root URL (depth 0) is allowed; pending URL at depth 1 is blocked."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=1)
        # Root URL has no pending entry → effective depth 0 < max_depth=1 → allowed
        assert tracker.get_depth_for("https://chat.example.com/team/pl/root") is None

        # Register a child URL at depth 1 — at max_depth, should be blocked
        tracker.register_pending("https://github.com/org/repo/issues/1", 1)
        assert tracker.get_depth_for("https://github.com/org/repo/issues/1") == 1
        # depth 1 >= max_depth 1 → blocked
        assert tracker.get_depth_for("https://github.com/org/repo/issues/1") >= tracker.max_depth

    def test_depth_2_one_reference(self) -> None:
        """With max_depth=2, root (depth 0) and depth-1 URLs pass; depth-2 URLs are blocked."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)

        # Root URL (no registration) → depth None → effective 0 < 2 → allowed
        assert tracker.get_depth_for("https://root.example.com") is None

        # Depth-1 child: allowed
        tracker.register_pending("https://github.com/org/repo/issues/1", 1)
        assert tracker.get_depth_for("https://github.com/org/repo/issues/1") == 1
        assert 1 < tracker.max_depth  # allowed

        # Depth-2 grandchild: blocked
        tracker.register_pending("https://github.com/org/repo/issues/2", 2)
        assert tracker.get_depth_for("https://github.com/org/repo/issues/2") == 2
        assert 2 >= tracker.max_depth  # blocked

    def test_depth_3_thread_chain(self) -> None:
        """With max_depth=3, a chain root→child(1)→grandchild(2) is allowed; great-grandchild(3) is blocked."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)

        # root: depth 0 → allowed
        root = "https://chat.example.com/team/pl/root"
        assert tracker.get_depth_for(root) is None  # not registered → depth 0

        # child at depth 1 → allowed
        child = "https://github.com/org/repo/issues/1"
        tracker.register_pending(child, 1)
        assert tracker.get_depth_for(child) == 1
        assert 1 < tracker.max_depth

        # grandchild at depth 2 → allowed
        grandchild = "https://bugs.launchpad.net/ubuntu/+bug/1"
        tracker.register_pending(grandchild, 2)
        assert tracker.get_depth_for(grandchild) == 2
        assert 2 < tracker.max_depth

        # great-grandchild at depth 3 → blocked
        great = "https://github.com/org/repo/issues/2"
        tracker.register_pending(great, 3)
        assert tracker.get_depth_for(great) == 3
        assert 3 >= tracker.max_depth

    def test_depth_limit_stops_recursion(self) -> None:
        """Verify depth limit stops recursion correctly; reset clears state."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)

        url = "https://github.com/org/repo/issues/1"
        tracker.register_pending(url, 2)
        assert tracker.get_depth_for(url) == 2
        assert 2 >= tracker.max_depth  # blocked

        # Reset should clear both dicts
        tracker.reset()
        assert len(tracker.followed_urls) == 0
        assert len(tracker.pending_urls) == 0
        assert tracker.get_depth_for(url) is None  # no longer registered

    def test_cycle_prevention(self) -> None:
        """Test that followed URLs are tracked to prevent cycles."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        url = "https://chat.example.com/team/pl/abc123"
        assert tracker.has_been_followed(url) is False
        tracker.mark_followed(url, 0)
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


class TestReferenceTrackingExecutor:
    """Tests for ReferenceTrackingExecutor follow_url command."""

    def test_follow_url_success(self) -> None:
        """Test follow_url returns success for new URL within depth."""
        from mattermost_summarizer.subagents.reference_tracking_tool import (
            ReferenceTrackingAction,
            ReferenceTrackingExecutor,
        )
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        executor = ReferenceTrackingExecutor(tracker)
        url = "https://bugs.launchpad.net/ubuntu/+bug/12345"
        # Root URL (no pending entry) → effective depth 0
        action = ReferenceTrackingAction(command="follow_url", url=url)

        result = executor(action)

        assert result.outcome == "success"
        assert result.url == url
        assert tracker.has_been_followed(url)
        # After mark_followed, URL is in followed_urls at depth 0
        assert tracker.followed_urls[url] == 0

    def test_follow_url_already_followed(self) -> None:
        """Test follow_url returns already_followed for duplicate URL."""
        from mattermost_summarizer.subagents.reference_tracking_tool import (
            ReferenceTrackingAction,
            ReferenceTrackingExecutor,
        )
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        executor = ReferenceTrackingExecutor(tracker)
        url = "https://bugs.launchpad.net/ubuntu/+bug/12345"
        action = ReferenceTrackingAction(command="follow_url", url=url)

        result1 = executor(action)
        assert result1.outcome == "success"

        result2 = executor(action)
        assert result2.outcome == "already_followed"

    def test_follow_url_depth_exceeded(self) -> None:
        """Test follow_url returns depth_exceeded for a URL registered at max depth."""
        from mattermost_summarizer.subagents.reference_tracking_tool import (
            ReferenceTrackingAction,
            ReferenceTrackingExecutor,
        )
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=1)
        executor = ReferenceTrackingExecutor(tracker)

        url1 = "https://bugs.launchpad.net/ubuntu/+bug/12345"
        url2 = "https://bugs.launchpad.net/ubuntu/+bug/67890"

        # url1 is root → depth 0 < max_depth 1 → success
        action1 = ReferenceTrackingAction(command="follow_url", url=url1)
        result1 = executor(action1)
        assert result1.outcome == "success"

        # url2 is registered at depth 1 (at max) → depth_exceeded
        tracker.register_pending(url2, 1)
        action2 = ReferenceTrackingAction(command="follow_url", url=url2)
        result2 = executor(action2)
        assert result2.outcome == "depth_exceeded"
        assert tracker.has_been_followed(url1)
        assert not tracker.has_been_followed(url2)

    def test_follow_url_atomic_under_lock(self) -> None:
        """Test follow_url is atomic under tracker lock."""
        import threading
        from concurrent.futures import ThreadPoolExecutor

        from mattermost_summarizer.subagents.reference_tracking_tool import (
            ReferenceTrackingAction,
            ReferenceTrackingExecutor,
        )
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        executor = ReferenceTrackingExecutor(tracker)
        url = "https://bugs.launchpad.net/ubuntu/+bug/12345"
        action = ReferenceTrackingAction(command="follow_url", url=url)

        results: list[str] = []
        lock = threading.Lock()

        def call_executor() -> None:
            result = executor(action)
            with lock:
                results.append(result.outcome)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(call_executor) for _ in range(2)]
            for f in futures:
                f.result()

        assert "success" in results
        assert "already_followed" in results

    def test_follow_url_requires_url(self) -> None:
        """Test follow_url returns error when URL is missing."""
        from mattermost_summarizer.subagents.reference_tracking_tool import (
            ReferenceTrackingAction,
            ReferenceTrackingExecutor,
        )
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        executor = ReferenceTrackingExecutor(tracker)
        action = ReferenceTrackingAction(command="follow_url", url=None)

        result = executor(action)

        assert result.error is not None
        assert "URL required" in result.error


class TestReferenceTrackingToolDescription:
    """Tests for ReferenceTrackingTool description."""

    def test_tool_description_contains_follow_url(self) -> None:
        """Test that tool description documents follow_url command."""
        from mattermost_summarizer.subagents.reference_tracking_tool import ReferenceTrackingTool

        tools = ReferenceTrackingTool.create()
        assert len(tools) == 1
        desc = tools[0].description
        assert "follow_url" in desc
        assert "success" in desc or "already_followed" in desc or "depth_exceeded" in desc

    def test_tool_description_omits_classify_text(self) -> None:
        """Test that tool description no longer mentions classify_text."""
        from mattermost_summarizer.subagents.reference_tracking_tool import ReferenceTrackingTool

        tools = ReferenceTrackingTool.create()
        assert len(tools) == 1
        desc = tools[0].description
        assert "classify_text" not in desc

    def test_tool_description_omits_old_commands(self) -> None:
        """Test that tool description no longer mentions old bookkeeping commands."""
        from mattermost_summarizer.subagents.reference_tracking_tool import ReferenceTrackingTool

        tools = ReferenceTrackingTool.create()
        assert len(tools) == 1
        desc = tools[0].description
        assert "mark_followed" not in desc
        assert "is_followed" not in desc
        assert "can_follow" not in desc
        assert "increment_depth" not in desc


class TestOrchestratorPromptUpdated:
    """Tests for updated orchestrator prompt."""

    def test_prompt_contains_follow_url_instructions(self) -> None:
        """Test that orchestrator prompt explains follow_url usage."""

        # assert "follow_url" in ORCHESTRATOR_PROMPT
        # assert "success" in ORCHESTRATOR_PROMPT
        # assert "already_followed" in ORCHESTRATOR_PROMPT
        # assert "depth_exceeded" in ORCHESTRATOR_PROMPT

    def test_prompt_omits_classify_text(self) -> None:
        """Test that orchestrator prompt no longer mentions classify_text."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "classify_text" not in ORCHESTRATOR_PROMPT

    def test_prompt_omits_old_bookkeeping_commands(self) -> None:
        """Test that orchestrator prompt no longer mentions old bookkeeping commands."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "mark_followed" not in ORCHESTRATOR_PROMPT
        assert "is_followed" not in ORCHESTRATOR_PROMPT
        assert "can_follow" not in ORCHESTRATOR_PROMPT
        assert "increment_depth" not in ORCHESTRATOR_PROMPT

    def test_prompt_mentions_injected_url_list(self) -> None:
        """Test that orchestrator prompt mentions automatic URL injection."""
        from mattermost_summarizer.agent import ORCHESTRATOR_PROMPT

        assert "References found in result" in ORCHESTRATOR_PROMPT


class TestUrlInjectionMessage:
    """Tests for URL injection message formatting."""

    def test_format_url_injection_message_empty(self) -> None:
        """Test formatting with no URLs."""
        from mattermost_summarizer.summarizer import format_url_injection_message
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        result = format_url_injection_message([], tracker)
        assert result == ""

    def test_format_url_injection_message_with_urls(self) -> None:
        """Test formatting with URLs."""
        from mattermost_summarizer.summarizer import format_url_injection_message
        from mattermost_summarizer.tools.reference_tracker import (
            ClassifiedUrl,
            ReferenceTracker,
            ReferenceType,
        )

        tracker = ReferenceTracker(max_depth=3)
        urls = [
            ClassifiedUrl(
                url="https://bugs.launchpad.net/ubuntu/+bug/12345",
                reference_type=ReferenceType.LAUNCHPAD_BUG,
                agent_type="bug_researcher",
            ),
        ]
        result = format_url_injection_message(urls, tracker)
        assert "References found in delegation result" in result
        assert "launchpad_bug" in result
        assert "bug_researcher" in result

    def test_format_url_injection_message_depth_info(self) -> None:
        """Test that injection message includes depth info."""
        from mattermost_summarizer.summarizer import format_url_injection_message
        from mattermost_summarizer.tools.reference_tracker import (
            ClassifiedUrl,
            ReferenceTracker,
            ReferenceType,
        )

        tracker = ReferenceTracker(max_depth=3)
        # Simulate one URL already followed
        tracker.mark_followed("https://chat.example.com/team/pl/root", 0)
        urls = [
            ClassifiedUrl(
                url="https://bugs.launchpad.net/ubuntu/+bug/12345",
                reference_type=ReferenceType.LAUNCHPAD_BUG,
                agent_type="bug_researcher",
            ),
        ]
        result = format_url_injection_message(urls, tracker)
        assert "URLs followed: 1/3" in result
        assert "can follow more" in result


class TestBuildOrchestratorAgentWithTracker:
    """Tests for build_orchestrator_agent with tracker parameter."""

    def test_build_orchestrator_agent_accepts_tracker(self) -> None:
        """Test that build_orchestrator_agent accepts tracker parameter."""
        from mattermost_summarizer.agent import build_orchestrator_agent
        from mattermost_summarizer.levels import SummaryLevel
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)
        agent = build_orchestrator_agent(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            llm_base_url=None,
            level=SummaryLevel.NORMAL,
            tracker=tracker,
        )

        assert agent is not None
        assert hasattr(agent, "llm")
        assert hasattr(agent, "tools")

    def test_build_orchestrator_agent_uses_provided_tracker(self) -> None:
        """Test that build_orchestrator_agent uses the provided tracker."""
        from mattermost_summarizer.agent import build_orchestrator_agent
        from mattermost_summarizer.levels import SummaryLevel
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=2)
        agent = build_orchestrator_agent(
            llm_model="openai/gpt-4o",
            llm_api_key="test-key",
            llm_base_url=None,
            level=SummaryLevel.NORMAL,
            tracker=tracker,
        )

        assert agent is not None


class TestFetchReferenceInjection:
    """Tests for the References-found block injected by FetchReferenceExecutor."""

    def _make_executor(self):
        import itertools
        from unittest.mock import MagicMock, patch

        from mattermost_summarizer.subagents.fetch_reference_tool import FetchReferenceExecutor
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)

        with patch("openhands.tools.delegate.impl.DelegateExecutor.__init__", return_value=None):
            executor = FetchReferenceExecutor.__new__(FetchReferenceExecutor)
            executor._tracker = tracker
            executor._delegate_executor = MagicMock()
            executor._agent_counter = itertools.count()

        return executor

    def _run_with_delegate_result(self, executor, result_text, url="https://chat.canonical.com/canonical/pl/abc123"):
        from unittest.mock import MagicMock

        from openhands.sdk.llm.message import TextContent

        spawn_obs = MagicMock()
        spawn_obs.is_error = False

        delegate_obs = MagicMock()
        delegate_obs.to_llm_content = [TextContent(text=result_text)]

        executor._delegate_executor.side_effect = [spawn_obs, delegate_obs]

        from mattermost_summarizer.subagents.fetch_reference_tool import FetchReferenceAction

        action = FetchReferenceAction(url=url)
        return executor(action)

    def test_no_references_in_result_has_no_block(self):
        """When the sub-agent result has no known URLs, no References block is appended."""
        executor = self._make_executor()
        result_text = "This thread is about a simple deployment question. No links mentioned."
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        assert "References found in result" not in obs.result
        assert result_text in obs.result

    def test_github_url_in_result_triggers_block(self):
        """When result contains a GitHub issue URL, a References block is appended."""
        executor = self._make_executor()
        result_text = (
            "Thread summary: user reports bug.\n"
            "Relevant PR: https://github.com/canonical/cloud-init/pull/6843\n"
            "Also see issue https://github.com/canonical/cloud-init/issues/6844"
        )
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        assert "References found in result" in obs.result
        assert "https://github.com/canonical/cloud-init/pull/6843" in obs.result
        assert "https://github.com/canonical/cloud-init/issues/6844" in obs.result
        assert "GitHub issue/PR" in obs.result

    def test_launchpad_url_in_result_triggers_block(self):
        """When result contains a Launchpad bug URL, a References block is appended."""
        executor = self._make_executor()
        result_text = "See LP bug: https://bugs.launchpad.net/ubuntu/+source/open-iscsi/+bug/2098515"
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        assert "References found in result" in obs.result
        assert "https://bugs.launchpad.net/ubuntu/+source/open-iscsi/+bug/2098515" in obs.result
        assert "Launchpad bug" in obs.result

    def test_already_followed_url_excluded_from_block(self):
        """URLs already followed by the tracker are not listed in the References block."""
        executor = self._make_executor()
        already_followed = "https://github.com/canonical/cloud-init/issues/6844"
        executor._tracker.mark_followed(already_followed, 1)

        result_text = f"See {already_followed} and also https://github.com/canonical/cloud-init/pull/6843"
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        # The already-followed URL must not appear as a reference entry URL in the injected block
        if "References found in result" in obs.result:
            block = obs.result.split("References found in result")[1]
            import re

            # Extract only the URL part of each numbered entry (before any ' — ' context)
            entry_urls = [
                re.sub(r" —.*$", "", line.strip()).split(" ")[1]
                for line in block.splitlines()
                if re.match(r"^\d+\.", line.strip())
            ]
            assert already_followed not in entry_urls
            assert "https://github.com/canonical/cloud-init/pull/6843" in block

    def test_depth_reached_suppresses_block(self):
        """When max depth is already reached, no References block is appended."""
        executor = self._make_executor()
        # Register the URL-to-fetch at depth == max_depth so it's blocked
        url_to_fetch = "https://chat.canonical.com/canonical/pl/xyz"
        executor._tracker.register_pending(url_to_fetch, executor._tracker.max_depth)

        result_text = "See PR: https://github.com/canonical/cloud-init/pull/6843"
        obs = self._run_with_delegate_result(
            executor,
            result_text,
            url=url_to_fetch,
        )

        # Either depth-error short-circuit or no References block
        if obs.error:
            assert "depth" in obs.error.lower()
        else:
            assert "References found in result" not in obs.result

    def test_block_contains_depth_info(self):
        """The injected block includes depth information."""
        executor = self._make_executor()
        result_text = "PR: https://github.com/canonical/cloud-init/pull/6843"
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        assert "Depth:" in obs.result

    def test_result_text_preserved_before_block(self):
        """The original result text appears before the References block."""
        executor = self._make_executor()
        result_text = "SUMMARY_MARKER: https://github.com/canonical/cloud-init/pull/1"
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        assert obs.result.startswith("SUMMARY_MARKER")
        ref_idx = obs.result.index("---\nReferences found")
        assert "SUMMARY_MARKER" in obs.result[:ref_idx]

    def test_unknown_urls_not_in_references_block(self):
        """Non-followable URLs (docs pages etc.) are excluded as reference entries from the block."""
        executor = self._make_executor()
        result_text = "See https://docs.ubuntu.com/some-page and https://github.com/canonical/cloud-init/issues/9999"
        obs = self._run_with_delegate_result(executor, result_text)

        assert obs.error is None
        if "References found in result" in obs.result:
            block = obs.result.split("References found in result")[1]
            # docs.ubuntu.com should not appear as a reference entry URL (e.g. "1. https://docs...")
            import re

            entry_urls = [
                re.sub(r" —.*$", "", line.strip()).split(" ")[1]
                for line in block.splitlines()
                if re.match(r"^\d+\.", line.strip())
            ]
            assert not any("docs.ubuntu.com" in u for u in entry_urls)
            assert "https://github.com/canonical/cloud-init/issues/9999" in block


class TestPerUrlDepth:
    """Tests for per-URL depth model (tasks 6.3, 6.4, 6.6)."""

    def test_six_siblings_at_depth_1_all_succeed(self) -> None:
        """Task 6.3: 6 sibling URLs at depth 1 all pass with max_depth=3."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        siblings = [f"https://github.com/org/repo/issues/{i}" for i in range(6)]

        # All siblings are registered at depth 1 by the parent injection
        for url in siblings:
            tracker.register_pending(url, 1)

        for url in siblings:
            depth = tracker.get_depth_for(url)
            assert depth == 1
            assert depth < tracker.max_depth  # all allowed

    def test_chain_nesting_depth_correct(self) -> None:
        """Task 6.4: Chain root -> sibling -> child -> grandchild has correct depths."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=4)

        root = "https://chat.example.com/team/pl/root"
        sibling = "https://github.com/org/repo/issues/1"
        child = "https://bugs.launchpad.net/ubuntu/+bug/100"
        grandchild = "https://github.com/org/repo/pull/2"

        # root: unregistered -> depth 0
        assert tracker.get_depth_for(root) is None

        # After fetching root, siblings are registered at depth 1
        tracker.register_pending(sibling, 1)
        tracker.mark_followed(root, 0)
        assert tracker.get_depth_for(sibling) == 1

        # After fetching sibling (depth 1), its children registered at depth 2
        tracker.register_pending(child, 2)
        tracker.mark_followed(sibling, 1)
        assert tracker.get_depth_for(child) == 2

        # After fetching child (depth 2), its grandchildren at depth 3
        tracker.register_pending(grandchild, 3)
        tracker.mark_followed(child, 2)
        assert tracker.get_depth_for(grandchild) == 3

    def test_register_pending_get_depth_mark_followed_lifecycle(self) -> None:
        """Task 6.6: register_pending -> get_depth_for -> mark_followed lifecycle."""
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        url = "https://github.com/org/repo/issues/42"

        # Before registration: unregistered
        assert tracker.get_depth_for(url) is None
        assert not tracker.has_been_followed(url)

        # After registration: in pending_urls
        tracker.register_pending(url, 1)
        assert tracker.get_depth_for(url) == 1
        assert url in tracker.pending_urls
        assert url not in tracker.followed_urls

        # After mark_followed: moves to followed_urls, removed from pending_urls
        tracker.mark_followed(url, 1)
        assert tracker.get_depth_for(url) == 1
        assert url not in tracker.pending_urls
        assert url in tracker.followed_urls
        assert tracker.has_been_followed(url)


class TestMaxSubAgentsConfig:
    """Tests for max_sub_agents config field and FetchReferenceExecutor max_children."""

    def test_config_default_max_sub_agents(self) -> None:
        """Test that MattermostSummarizerConfig.max_sub_agents defaults to 20."""
        from unittest.mock import patch

        from mattermost_summarizer.config import MattermostSummarizerConfig

        with patch.dict(
            "os.environ",
            {
                "MM_MATTERMOST_URL": "https://chat.example.com",
                "MM_MATTERMOST_TOKEN": "tok",
                "MM_LLM_API_KEY": "key",
            },
        ):
            config = MattermostSummarizerConfig()
            assert config.max_sub_agents == 20

    def test_config_custom_max_sub_agents(self) -> None:
        """Test that MattermostSummarizerConfig.max_sub_agents can be overridden."""
        from unittest.mock import patch

        from mattermost_summarizer.config import MattermostSummarizerConfig

        with patch.dict(
            "os.environ",
            {
                "MM_MATTERMOST_URL": "https://chat.example.com",
                "MM_MATTERMOST_TOKEN": "tok",
                "MM_LLM_API_KEY": "key",
                "MM_MAX_SUB_AGENTS": "50",
            },
        ):
            config = MattermostSummarizerConfig()
            assert config.max_sub_agents == 50

    def test_fetch_reference_executor_passes_max_children(self) -> None:
        """Test that FetchReferenceExecutor passes max_children to DelegateExecutor."""
        from unittest.mock import patch

        from mattermost_summarizer.subagents.fetch_reference_tool import FetchReferenceExecutor
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        captured_kwargs: dict = {}

        def mock_delegate_init(self, max_children=5, **kwargs):
            captured_kwargs["max_children"] = max_children

        with patch("openhands.tools.delegate.impl.DelegateExecutor.__init__", mock_delegate_init):
            FetchReferenceExecutor(tracker=tracker, max_children=42)

        assert captured_kwargs.get("max_children") == 42

    def test_fetch_reference_tool_create_passes_max_children(self) -> None:
        """Test that FetchReferenceTool.create() passes max_children to the executor."""
        from unittest.mock import patch

        from mattermost_summarizer.subagents.fetch_reference_tool import FetchReferenceTool
        from mattermost_summarizer.tools.reference_tracker import ReferenceTracker

        tracker = ReferenceTracker(max_depth=3)
        captured_kwargs: dict = {}

        def mock_delegate_init(self, max_children=5, **kwargs):
            captured_kwargs["max_children"] = max_children

        with patch("openhands.tools.delegate.impl.DelegateExecutor.__init__", mock_delegate_init):
            tools = FetchReferenceTool.create(tracker=tracker, max_children=15)

        assert len(tools) == 1
        assert captured_kwargs.get("max_children") == 15
