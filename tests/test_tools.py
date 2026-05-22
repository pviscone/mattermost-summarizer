"""Tests for OpenHands tools."""


class TestFinishTool:
    def test_finish_observation_to_llm_content(self) -> None:
        from mattermost_summarizer.levels.base import (
            SummarizerFinishObservation,
        )

        obs = SummarizerFinishObservation(success=True, summary_provided=True)
        content = obs.to_llm_content
        assert len(content) == 1
        assert "Summary complete" in content[0].text


class TestFetchThreadTool:
    def test_fetch_thread_observation_format(self) -> None:
        from mattermost_summarizer.tools.fetch_thread.impl import (
            FetchThreadObservation,
        )

        obs = FetchThreadObservation(
            root_post={
                "id": "root123",
                "author_name": "alice",
                "message": "Hello everyone!",
                "created_at": "2026-05-21T10:00:00",
            },
            replies=[
                {
                    "id": "reply1",
                    "author_name": "bob",
                    "message": "Hi alice!",
                    "created_at": "2026-05-21T10:05:00",
                }
            ],
            channel_id="channel1",
            channel_name="general",
            total_replies=1,
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Thread" in text
        assert "general" in text
        assert "alice" in text
        assert "Hello everyone" in text
        assert "bob" in text
        assert "Hi alice" in text

    def test_fetch_thread_observation_error(self) -> None:
        from mattermost_summarizer.tools.fetch_thread.impl import (
            FetchThreadObservation,
        )

        obs = FetchThreadObservation(
            root_post={},
            replies=[],
            channel_id="",
            channel_name=None,
            total_replies=0,
            error="Connection failed",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text


class TestGetUserTool:
    def test_get_user_observation_format(self) -> None:
        from mattermost_summarizer.tools.get_user.impl import GetUserObservation

        obs = GetUserObservation(
            user_id="user123",
            username="jdoe",
            display_name="Jane Doe",
            email="jane@example.com",
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "@jdoe" in text
        assert "Jane Doe" in text

    def test_get_user_observation_error(self) -> None:
        from mattermost_summarizer.tools.get_user.impl import GetUserObservation

        obs = GetUserObservation(
            user_id="user123",
            username="",
            display_name="",
            error="User not found",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text


class TestFetchChannelTool:
    def test_fetch_channel_observation_format(self) -> None:
        from mattermost_summarizer.tools.fetch_channel.impl import (
            FetchChannelObservation,
        )

        obs = FetchChannelObservation(
            channel_id="channel123",
            name="general",
            display_name="General",
            purpose="Company-wide discussion",
            team_name="myteam",
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "#General" in text
        assert "myteam" in text
        assert "Company-wide" in text

    def test_fetch_channel_observation_error(self) -> None:
        from mattermost_summarizer.tools.fetch_channel.impl import (
            FetchChannelObservation,
        )

        obs = FetchChannelObservation(
            channel_id="invalid",
            name="",
            display_name="",
            error="Channel not found",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text

    def test_fetch_channel_by_name_lookup(self) -> None:
        """Test that channel_name + team_name triggers lookup to get channel_id."""
        from unittest.mock import MagicMock

        from mattermost_summarizer.models import Channel
        from mattermost_summarizer.tools.fetch_channel.impl import (
            FetchChannelAction,
            FetchChannelExecutor,
        )

        mock_channel = Channel(
            id="channel123",
            name="cloud-init",
            display_name="cloud-init",
            purpose="cloud-init discussion",
        )

        mock_client = MagicMock()
        mock_client.get_team_id_by_name.return_value = "team1"
        mock_client.get_channel_by_name.return_value = mock_channel
        mock_client.get_channel.return_value = mock_channel

        executor = FetchChannelExecutor(client=mock_client)
        result = executor(FetchChannelAction(channel_name="cloud-init", team_name="ubuntu"))

        assert result.error is None
        assert result.name == "cloud-init"
        assert result.channel_id == "channel123"
        mock_client.get_team_id_by_name.assert_called_once_with("ubuntu")
        mock_client.get_channel_by_name.assert_called_once_with("team1", "cloud-init")
        mock_client.get_channel.assert_called_once_with("channel123")


class TestFetchFileTool:
    def test_fetch_file_observation_text_file(self) -> None:
        from mattermost_summarizer.tools.fetch_file.impl import (
            FetchFileObservation,
        )

        obs = FetchFileObservation(
            file_text_content="Hello, world!",
            is_binary=False,
            mime_type="text/plain",
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Hello, world!" in text

    def test_fetch_file_observation_binary_file(self) -> None:
        from mattermost_summarizer.tools.fetch_file.impl import (
            FetchFileObservation,
        )

        obs = FetchFileObservation(
            file_text_content=None,
            is_binary=True,
            mime_type="image/png",
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Binary file" in text
        assert "image/png" in text
        assert "not readable" in text

    def test_fetch_file_observation_error(self) -> None:
        from mattermost_summarizer.tools.fetch_file.impl import (
            FetchFileObservation,
        )

        obs = FetchFileObservation(
            file_text_content=None,
            is_binary=False,
            mime_type=None,
            error="File not found",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text
        assert "File not found" in content[0].text


class TestFetchLaunchpadBugTool:
    def test_fetch_launchpad_bug_observation_format(self) -> None:
        from mattermost_summarizer.tools.fetch_launchpad_bug.impl import (
            FetchLaunchpadBugObservation,
        )

        obs = FetchLaunchpadBugObservation(
            title="Bug in package X",
            description="This package has a critical bug",
            status="Triaged",
            importance="High",
            tags=["security", "regression"],
            comments=["Comment 1", "Comment 2"],
            total_comments=2,
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Bug in package X" in text
        assert "Triaged" in text
        assert "High" in text

    def test_fetch_launchpad_bug_observation_error(self) -> None:
        from mattermost_summarizer.tools.fetch_launchpad_bug.impl import (
            FetchLaunchpadBugObservation,
        )

        obs = FetchLaunchpadBugObservation(
            title=None,
            description=None,
            status=None,
            importance=None,
            tags=None,
            comments=None,
            total_comments=None,
            error="Bug not found",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text
        assert "Bug not found" in content[0].text

    def test_fetch_launchpad_bug_url_with_plus_in_path_segments(self) -> None:
        from mattermost_summarizer.tools.fetch_launchpad_bug.impl import (
            FetchLaunchpadBugAction,
            FetchLaunchpadBugExecutor,
        )

        executor = FetchLaunchpadBugExecutor(client=None)
        result = executor(
            FetchLaunchpadBugAction(bug_url_or_id="https://bugs.launchpad.net/ubuntu/+source/open-iscsi/+bug/2098515")
        )
        assert result.error is None or "rate" in result.error.lower() or "not found" in result.error.lower()

    def test_fetch_launchpad_bug_url_parsing(self) -> None:
        from mattermost_summarizer.tools.fetch_launchpad_bug.impl import (
            FetchLaunchpadBugAction,
            FetchLaunchpadBugExecutor,
        )

        executor = FetchLaunchpadBugExecutor(client=None)

        valid_urls = [
            "https://bugs.launchpad.net/ubuntu/+bug/1234567",
            "https://bugs.launchpad.net/ubuntu-security/+bug/1234567",
            "https://bugs.launchpad.net/ubuntu/+source/open-iscsi/+bug/2098515",
            "https://api.launchpad.net/1.0/bugs/999999",
            "1234567",
        ]

        for url in valid_urls:
            result = executor(FetchLaunchpadBugAction(bug_url_or_id=url))
            assert result.error != "Invalid bug URL or ID", f"Failed to parse: {url}"


class TestFetchGitHubIssueTool:
    def test_fetch_github_issue_observation_format(self) -> None:
        from mattermost_summarizer.tools.fetch_github_issue.impl import (
            FetchGitHubIssueObservation,
        )

        obs = FetchGitHubIssueObservation(
            title="Bug in feature Y",
            body="This feature has a critical bug",
            state="open",
            labels=["bug", "high-priority"],
            assignees=["alice", "bob"],
            author="charlie",
            created_at="2026-05-01T10:00:00Z",
            updated_at="2026-05-15T12:00:00Z",
            comments=["First comment", "Second comment"],
            total_comments=2,
            is_pull_request=False,
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Bug in feature Y" in text
        assert "open" in text
        assert "charlie" in text

    def test_fetch_github_issue_observation_pr_format(self) -> None:
        from mattermost_summarizer.tools.fetch_github_issue.impl import (
            FetchGitHubIssueObservation,
        )

        obs = FetchGitHubIssueObservation(
            title="Add new feature",
            body="This PR adds a new feature",
            state="open",
            labels=[],
            assignees=["alice"],
            author="bob",
            created_at="2026-05-01T10:00:00Z",
            updated_at="2026-05-15T12:00:00Z",
            comments=[],
            total_comments=0,
            is_pull_request=True,
            review_comments=["LGTM", "Nice implementation"],
            merge_status="clean",
        )

        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "PR" in text
        assert "LGTM" in text
        assert "clean" in text

    def test_fetch_github_issue_observation_error(self) -> None:
        from mattermost_summarizer.tools.fetch_github_issue.impl import (
            FetchGitHubIssueObservation,
        )

        obs = FetchGitHubIssueObservation(
            title=None,
            body=None,
            state=None,
            labels=None,
            assignees=None,
            author=None,
            created_at=None,
            updated_at=None,
            comments=None,
            total_comments=None,
            is_pull_request=False,
            error="Issue not found",
        )

        content = obs.to_llm_content
        assert "Error" in content[0].text
        assert "Issue not found" in content[0].text
