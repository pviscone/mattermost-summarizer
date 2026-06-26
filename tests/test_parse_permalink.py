"""Tests for URL parsing utility."""

import pytest

from mattermost_summarizer.utils import (
    PermalinkError,
    parse_channel_url,
    parse_message_url,
    parse_permalink,
    parse_time_point,
)


class TestParsePermalink:
    def test_valid_permalink_with_team(self) -> None:
        url = "https://chat.canonical.com/canonical/pl/injbzc9x1igkmk6icenahhj7ho"
        result = parse_permalink(url)
        assert result == "injbzc9x1igkmk6icenahhj7ho"

    def test_valid_permalink_case_insensitive_pl(self) -> None:
        url = "https://example.com/team/PL/ABC123"
        result = parse_permalink(url)
        assert result == "ABC123"

    def test_valid_permalink_uppercase_post_id(self) -> None:
        url = "https://example.com/team/pl/ABC123XYZ"
        result = parse_permalink(url)
        assert result == "ABC123XYZ"

    def test_valid_permalink_api_post_path(self) -> None:
        url = "https://example.com/api/v4/posts/ABC123XYZ"
        result = parse_permalink(url)
        assert result == "ABC123XYZ"

    def test_empty_url_raises_error(self) -> None:
        with pytest.raises(PermalinkError, match="Empty URL"):
            parse_permalink("")

    def test_invalid_format_raises_error(self) -> None:
        url = "https://chat.canonical.com/canonical/channels/general/123"
        with pytest.raises(PermalinkError, match="Not a valid Mattermost permalink"):
            parse_permalink(url)

    def test_url_without_pl_path_raises_error(self) -> None:
        url = "https://example.com/team/threads/abc123"
        with pytest.raises(PermalinkError, match="Not a valid Mattermost permalink"):
            parse_permalink(url)

    def test_url_without_path_raises_error(self) -> None:
        url = "https://chat.canonical.com"
        with pytest.raises(PermalinkError, match="Not a valid Mattermost permalink"):
            parse_permalink(url)

    def test_invalid_url_format_raises_error(self) -> None:
        url = "not-a-url-at-all"
        with pytest.raises(PermalinkError, match="Invalid URL format"):
            parse_permalink(url)


class TestParseChannelUrl:
    def test_valid_channel_url(self) -> None:
        url = "https://chat.canonical.com/canonical/channels/general"
        team_name, channel_name = parse_channel_url(url)

        assert team_name == "canonical"
        assert channel_name == "general"

    def test_invalid_channel_url_raises_error(self) -> None:
        with pytest.raises(PermalinkError, match="Not a valid Mattermost channel URL"):
            parse_channel_url("https://chat.canonical.com/canonical/pl/post123")


class TestParseMessageUrl:
    def test_valid_private_group_url(self) -> None:
        url = "https://chat.canonical.com/canonical/messages/group-channel-name"
        team_name, channel_name = parse_message_url(url)

        assert team_name == "canonical"
        assert channel_name == "group-channel-name"

    def test_valid_private_group_url_strips_at_prefix(self) -> None:
        url = "https://chat.canonical.com/canonical/messages/@group-channel-name"
        team_name, channel_name = parse_message_url(url)

        assert team_name == "canonical"
        assert channel_name == "group-channel-name"

    def test_invalid_message_url_raises_error(self) -> None:
        with pytest.raises(PermalinkError, match="Not a valid Mattermost direct/group message URL"):
            parse_message_url("https://chat.canonical.com/canonical/channels/general")


class TestParseTimePoint:
    def test_parse_naive_iso_time(self) -> None:
        parsed = parse_time_point("2026-06-26T10:00:00")
        assert parsed.isoformat() == "2026-06-26T10:00:00"

    def test_parse_utc_z_time(self) -> None:
        parsed = parse_time_point("2026-06-26T10:00:00Z")
        assert parsed.isoformat() == "2026-06-26T10:00:00"
