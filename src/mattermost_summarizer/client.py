"""Mattermost API client using httpx."""

from datetime import datetime
from typing import Any, cast

import httpx

from mattermost_summarizer.exceptions import (
    AuthenticationError,
    ChannelNotFoundError,
    FileNotFoundError,
    ThreadNotFoundError,
    UserNotFoundError,
)
from mattermost_summarizer.models import (
    Channel,
    PostData,
    PostThread,
    ReactionData,
    UserProfile,
)


class MattermostClient:
    """Sync HTTP client for Mattermost API v4.

    All methods are lazy — no network calls until invoked.
    Shared instance across tool executors for connection pooling.
    """

    def __init__(self, base_url: str, token: str) -> None:
        """Initialize the Mattermost client.

        Args:
            base_url: Mattermost server URL (e.g., https://chat.canonical.com)
            token: Bearer token for authentication
        """
        self._http = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/api/v4",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._user_cache: dict[str, UserProfile] = {}

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        self._http.close()

    def get_post_thread(self, post_id: str) -> PostThread:
        """Fetch a complete thread (root post + all replies).

        Args:
            post_id: The root post ID

        Returns:
            PostThread with root post, replies, and channel info

        Raises:
            ThreadNotFoundError: If the post doesn't exist (404)
            AuthenticationError: If unauthorized (401)
        """
        response = self._http.get(f"/posts/{post_id}/thread")

        if response.status_code == 401:
            raise AuthenticationError("Mattermost API authentication failed. Check your token.")
        if response.status_code == 404:
            raise ThreadNotFoundError(f"Post not found: {post_id}")

        response.raise_for_status()
        data = response.json()

        posts = data.get("posts", {})
        order = data.get("order", [])
        if order:
            root_id = order[0]
        else:
            root_id = next(
                (pid for pid, p in posts.items() if p.get("root_id") == "" or p.get("root_id") == pid),
                post_id,
            )
        if root_id not in posts:
            raise ThreadNotFoundError(f"Root post not found: {root_id}")

        root_post = self._parse_post(posts[root_id])

        replies: list[PostData] = []
        for pid, post_data in posts.items():
            if pid != root_id:
                replies.append(self._parse_post(post_data))

        replies.sort(key=lambda p: p.created_at)

        channel_id = posts[root_id].get("channel_id", "") or data.get("channel_id", "")
        channel_name = data.get("channel_name")
        if channel_id and not channel_name:
            try:
                channel_response = self._http.get(f"/channels/{channel_id}")
                if channel_response.is_success:
                    channel_name = channel_response.json().get("name")
            except Exception:
                pass

        return PostThread(
            root=root_post,
            replies=replies,
            channel_id=channel_id,
            channel_name=channel_name,
            total_replies=len(replies),
        )

    def get_channel_posts(self, channel_id: str, per_page: int = 200) -> list[PostData]:
        """Fetch all posts for a channel, sorted chronologically."""
        posts_by_id: dict[str, PostData] = {}
        page = 0

        while True:
            response = self._http.get(
                f"/channels/{channel_id}/posts",
                params={"page": page, "per_page": per_page},
            )

            if response.status_code == 401:
                raise AuthenticationError("Mattermost API authentication failed. Check your token.")
            if response.status_code == 404:
                raise ChannelNotFoundError(f"Channel not found: {channel_id}")

            response.raise_for_status()
            data = response.json()

            posts = data.get("posts", {})
            order = data.get("order", [])
            ordered_ids = order if order else list(posts.keys())

            for post_id in ordered_ids:
                post_data = posts.get(post_id)
                if post_data is not None and post_id not in posts_by_id:
                    posts_by_id[post_id] = self._parse_post(post_data)

            if len(ordered_ids) < per_page:
                break

            page += 1

        return sorted(posts_by_id.values(), key=lambda post: post.created_at)

    def get_user(self, user_id: str) -> UserProfile:
        """Fetch a user profile by ID.

        Args:
            user_id: The user ID

        Returns:
            UserProfile with user details

        Raises:
            UserNotFoundError: If user doesn't exist (404)
            AuthenticationError: If unauthorized (401)
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        response = self._http.get(f"/users/{user_id}")

        if response.status_code == 401:
            raise AuthenticationError("Mattermost API authentication failed. Check your token.")
        if response.status_code == 404:
            raise UserNotFoundError(f"User not found: {user_id}")

        response.raise_for_status()
        data = response.json()

        profile = UserProfile(
            id=data["id"],
            username=data.get("username", ""),
            display_name=data.get("display_name")
            or data.get("first_name")
            or data.get("nickname")
            or data.get("username", ""),
            email=data.get("email"),
            nickname=data.get("nickname"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
        )

        self._user_cache[user_id] = profile
        return profile

    def get_channel(self, channel_id: str) -> Channel:
        """Fetch a channel by ID.

        Args:
            channel_id: The channel ID

        Returns:
            Channel with details

        Raises:
            ChannelNotFoundError: If channel doesn't exist (404)
            AuthenticationError: If unauthorized (401)
        """
        response = self._http.get(f"/channels/{channel_id}")

        if response.status_code == 401:
            raise AuthenticationError("Mattermost API authentication failed. Check your token.")
        if response.status_code == 404:
            raise ChannelNotFoundError(f"Channel not found: {channel_id}")

        response.raise_for_status()
        data = response.json()

        team_name = None
        if "team_name" in data:
            team_name = data["team_name"]
        elif "team_id" in data:
            try:
                team_response = self._http.get(f"/teams/{data['team_id']}")
                if team_response.is_success:
                    team_name = team_response.json().get("name")
            except Exception:
                pass

        return Channel(
            id=data["id"],
            name=data.get("name", ""),
            display_name=data.get("display_name", ""),
            purpose=data.get("purpose"),
            header=data.get("header"),
            team_name=team_name,
            type=data.get("type", "O"),
        )

    def get_channel_by_name(self, team_name: str, channel_name: str) -> Channel:
        """Fetch a channel by name within a specific team.

        Args:
            team_name: The team slug/name from the Mattermost URL
            channel_name: The channel name (not display name)

        Returns:
            Channel with details

        Raises:
            ChannelNotFoundError: If channel doesn't exist (404)
            AuthenticationError: If unauthorized (401)
        """
        response = self._http.get(f"/teams/name/{team_name}/channels/name/{channel_name}")

        if response.status_code == 401:
            raise AuthenticationError("Mattermost API authentication failed. Check your token.")
        if response.status_code == 404:
            raise ChannelNotFoundError(f"Channel not found: {channel_name}")

        response.raise_for_status()
        return self._parse_channel(response.json())

    def get_team_id_by_name(self, team_name: str) -> str | None:
        """Look up a team ID by team name.

        Args:
            team_name: The team name

        Returns:
            Team ID if found, None otherwise
        """
        try:
            response = self._http.get(f"/teams/name/{team_name}")
            if response.is_success:
                return cast(str | None, response.json().get("id"))
        except Exception:
            pass
        return None

    def _parse_channel(self, data: dict[str, object]) -> Channel:
        """Parse raw channel data into a Channel model."""
        team_name = None
        if "team_name" in data:
            team_name = data["team_name"]
        elif "team_id" in data:
            try:
                team_response = self._http.get(f"/teams/{data['team_id']}")
                if team_response.is_success:
                    team_name = team_response.json().get("name")
            except Exception:
                pass

        return Channel(
            id=cast(str, data["id"]),
            name=cast(str, data.get("name", "")),
            display_name=cast(str, data.get("display_name", "")),
            purpose=cast(str | None, data.get("purpose")),
            header=cast(str | None, data.get("header")),
            team_name=cast(str | None, team_name),
            type=cast(str, data.get("type", "O")),
        )

    def get_file(self, file_id: str) -> tuple[bytes, str]:
        """Fetch a file attachment by ID.

        Args:
            file_id: The file ID

        Returns:
            Tuple of (file content bytes, content_type)

        Raises:
            FileNotFoundError: If file doesn't exist (404)
            AuthenticationError: If unauthorized (401)
        """
        response = self._http.get(f"/files/{file_id}")

        if response.status_code == 401:
            raise AuthenticationError("Mattermost API authentication failed. Check your token.")
        if response.status_code == 404:
            raise FileNotFoundError(f"File not found: {file_id}")

        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        return response.content, content_type

    def _parse_post(self, data: dict[str, Any]) -> PostData:
        """Parse a raw post dict into a PostData model."""
        reactions: list[ReactionData] = []
        metadata = data.get("metadata", {})
        if metadata.get("reactions"):
            for r in metadata["reactions"]:
                reactions.append(
                    ReactionData(
                        user_id=r.get("user_id", ""),
                        emoji_name=r.get("emoji_name", ""),
                        create_at=datetime.fromtimestamp(r.get("create_at", 0) / 1000),
                    )
                )

        return PostData(
            id=data["id"],
            author_id=data.get("user_id", ""),
            author_username=None,
            author_display_name=None,
            message=data.get("message", ""),
            created_at=datetime.fromtimestamp(data.get("create_at", 0) / 1000),
            reply_count=data.get("reply_count", 0),
            root_id=data.get("root_id", ""),
            reactions=reactions,
            attachments=data.get("file_ids", []),
            props=data.get("props", {}),
        )

    def __enter__(self) -> "MattermostClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
