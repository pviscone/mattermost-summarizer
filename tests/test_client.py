"""Tests for MattermostClient using pytest-httpserver."""

import pytest
from pytest_httpserver import HTTPServer

from mattermost_summarizer.client import MattermostClient
from mattermost_summarizer.exceptions import (
    AuthenticationError,
    ChannelNotFoundError,
    ThreadNotFoundError,
    UserNotFoundError,
)


@pytest.fixture
def client(httpserver: HTTPServer) -> MattermostClient:
    return MattermostClient(
        base_url=f"http://{httpserver.host}:{httpserver.port}",
        token="test-token-abc123",
    )


class TestMattermostClientGetPostThread:
    def test_get_post_thread_success(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        thread_response = {
            "posts": {
                "root123": {
                    "id": "root123",
                    "user_id": "user1",
                    "message": "Root post content",
                    "create_at": 1716288000000,
                    "reply_count": 1,
                },
                "reply1": {
                    "id": "reply1",
                    "user_id": "user2",
                    "message": "Reply content",
                    "create_at": 1716288300000,
                },
            },
            "thread_id": "root123",
            "root_id": "root123",
            "channel_id": "channel1",
            "channel_name": "general",
        }
        httpserver.expect_oneshot_request("/api/v4/posts/root123/thread", method="GET").respond_with_json(
            thread_response
        )

        user1_response = {"id": "user1", "username": "alice", "display_name": "Alice Smith"}
        user2_response = {"id": "user2", "username": "bob", "display_name": "Bob Jones"}
        httpserver.expect_oneshot_request("/api/v4/users/user1", method="GET").respond_with_json(user1_response)
        httpserver.expect_oneshot_request("/api/v4/users/user2", method="GET").respond_with_json(user2_response)

        thread = client.get_post_thread("root123")

        assert thread.root.id == "root123"
        assert thread.root.message == "Root post content"
        assert thread.root.author_id == "user1"
        assert len(thread.replies) == 1
        assert thread.replies[0].author_id == "user2"
        assert thread.channel_name == "general"
        assert thread.total_replies == 1

    def test_get_post_thread_not_found(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        httpserver.expect_oneshot_request("/api/v4/posts/nonexistent/thread", method="GET").respond_with_json(
            {"message": "Not found"}, status=404
        )

        with pytest.raises(ThreadNotFoundError, match="Post not found"):
            client.get_post_thread("nonexistent")

    def test_get_post_thread_unauthorized(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        httpserver.expect_oneshot_request("/api/v4/posts/post123/thread", method="GET").respond_with_json(
            {"message": "Unauthorized"}, status=401
        )

        with pytest.raises(AuthenticationError):
            client.get_post_thread("post123")


class TestMattermostClientGetChannelPosts:
    def test_get_channel_posts_returns_chronological_order(
        self, client: MattermostClient, httpserver: HTTPServer
    ) -> None:
        channel_posts_response = {
            "posts": {
                "post2": {
                    "id": "post2",
                    "user_id": "user2",
                    "message": "Later message",
                    "create_at": 1716288300000,
                    "root_id": "post1",
                },
                "post1": {
                    "id": "post1",
                    "user_id": "user1",
                    "message": "Earlier message",
                    "create_at": 1716288000000,
                    "root_id": "",
                },
            },
            "order": ["post2", "post1"],
        }
        httpserver.expect_oneshot_request("/api/v4/channels/channel123/posts", method="GET").respond_with_json(
            channel_posts_response
        )

        posts = client.get_channel_posts("channel123")

        assert [post.id for post in posts] == ["post1", "post2"]
        assert posts[0].message == "Earlier message"
        assert posts[1].root_id == "post1"


class TestMattermostClientGetUser:
    def test_get_user_success(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        user_response = {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
            "email": "test@example.com",
            "nickname": "Tester",
        }
        httpserver.expect_oneshot_request("/api/v4/users/user123", method="GET").respond_with_json(user_response)

        user = client.get_user("user123")

        assert user.id == "user123"
        assert user.username == "testuser"
        assert user.display_name == "Test User"
        assert user.email == "test@example.com"
        assert user.nickname == "Tester"

    def test_get_user_caches_result(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        user_response = {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
        }
        httpserver.expect_oneshot_request("/api/v4/users/user123", method="GET").respond_with_json(user_response)

        user1 = client.get_user("user123")
        user2 = client.get_user("user123")

        assert user1.id == user2.id
        assert user1.username == user2.username

    def test_get_user_not_found(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        httpserver.expect_oneshot_request("/api/v4/users/nonexistent", method="GET").respond_with_json(
            {"message": "Not found"}, status=404
        )

        with pytest.raises(UserNotFoundError, match="User not found"):
            client.get_user("nonexistent")


class TestMattermostClientGetChannel:
    def test_get_channel_success(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        channel_response = {
            "id": "channel123",
            "name": "general",
            "display_name": "General",
            "purpose": "Company-wide discussion",
            "header": "Welcome!",
            "type": "O",
            "team_id": "team1",
        }
        httpserver.expect_oneshot_request("/api/v4/channels/channel123", method="GET").respond_with_json(
            channel_response
        )

        channel = client.get_channel("channel123")

        assert channel.id == "channel123"
        assert channel.name == "general"
        assert channel.display_name == "General"
        assert channel.purpose == "Company-wide discussion"
        assert channel.team_name is None

    def test_get_channel_with_team(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        channel_response = {
            "id": "channel123",
            "name": "general",
            "display_name": "General",
            "type": "O",
            "team_id": "team1",
        }
        team_response = {
            "id": "team1",
            "name": "myteam",
        }
        httpserver.expect_oneshot_request("/api/v4/channels/channel123", method="GET").respond_with_json(
            channel_response
        )
        httpserver.expect_oneshot_request("/api/v4/teams/team1", method="GET").respond_with_json(team_response)

        channel = client.get_channel("channel123")

        assert channel.id == "channel123"
        assert channel.team_name == "myteam"

    def test_get_channel_not_found(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        httpserver.expect_oneshot_request("/api/v4/channels/nonexistent", method="GET").respond_with_json(
            {"message": "Not found"}, status=404
        )

        with pytest.raises(ChannelNotFoundError, match="Channel not found"):
            client.get_channel("nonexistent")


class TestMattermostClientGetChannelByName:
    def test_get_channel_by_name_success(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        channel_response = {
            "id": "channel123",
            "name": "cloud-init",
            "display_name": "cloud-init",
            "purpose": "cloud-init discussion",
            "header": "Channel for cloud-init",
            "type": "O",
        }
        httpserver.expect_oneshot_request(
            "/api/v4/teams/name/ubuntu/channels/name/cloud-init", method="GET"
        ).respond_with_json(channel_response)

        channel = client.get_channel_by_name("ubuntu", "cloud-init")

        assert channel.id == "channel123"
        assert channel.name == "cloud-init"
        assert channel.display_name == "cloud-init"
        assert channel.purpose == "cloud-init discussion"

    def test_get_channel_by_name_with_team(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        channel_response = {
            "id": "channel123",
            "name": "cloud-init",
            "display_name": "cloud-init",
            "type": "O",
            "team_id": "team1",
            "team_name": "ubuntu",
        }
        httpserver.expect_oneshot_request(
            "/api/v4/teams/name/ubuntu/channels/name/cloud-init", method="GET"
        ).respond_with_json(channel_response)

        channel = client.get_channel_by_name("ubuntu", "cloud-init")

        assert channel.id == "channel123"
        assert channel.team_name == "ubuntu"

    def test_get_channel_by_name_not_found(self, client: MattermostClient, httpserver: HTTPServer) -> None:
        httpserver.expect_oneshot_request(
            "/api/v4/teams/name/nonexistent/channels/name/nonexistent", method="GET"
        ).respond_with_json({"message": "Not found"}, status=404)

        with pytest.raises(ChannelNotFoundError, match="Channel not found"):
            client.get_channel_by_name("nonexistent", "nonexistent")
