"""Data models for mattermost-summarizer.

This module re-exports types from the levels package for backward compatibility.
The actual data models (PostData, PostThread, Channel, UserProfile, ReactionData)
are defined here. SummaryResult and SummaryMeta are re-exported from levels/.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from mattermost_summarizer.levels import (
    AnySummaryResult,
    BriefSummaryResult,
    DetailedSummaryResult,
    NormalSummaryResult,
    SummaryMeta,
    SummaryResultBase,
)

__all__ = [
    "PostData",
    "PostThread",
    "Channel",
    "UserProfile",
    "ReactionData",
    "SummaryMeta",
    "SummaryResult",
    "SummaryResultBase",
    "AnySummaryResult",
    "BriefSummaryResult",
    "NormalSummaryResult",
    "DetailedSummaryResult",
]

SummaryResult = NormalSummaryResult


class PostData(BaseModel):
    """A single post in a Mattermost thread."""

    id: str
    author_id: str
    author_username: str | None = None
    author_display_name: str | None = None
    message: str
    created_at: datetime
    reply_count: int = 0
    root_id: str = ""
    # ID of the post this post is directly replying to (parent). May be the root_id
    # for simple thread replies or a specific post id when replying to another reply.
    in_reply_to: str | None = None
    reactions: list[ReactionData] = []
    attachments: list[str] = []
    props: dict[str, Any] = {}


class ReactionData(BaseModel):
    """A reaction to a post."""

    user_id: str
    emoji_name: str
    create_at: datetime


class PostThread(BaseModel):
    """A complete thread (root post + replies)."""

    root: PostData
    replies: list[PostData] = []
    channel_id: str
    channel_name: str | None = None
    total_replies: int = 0


class UserProfile(BaseModel):
    """A Mattermost user profile."""

    id: str
    username: str
    display_name: str
    email: str | None = None
    nickname: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class Channel(BaseModel):
    """A Mattermost channel."""

    id: str
    name: str
    display_name: str
    purpose: str | None = None
    header: str | None = None
    team_name: str | None = None
    type: str = "O"  # O=public, P=private, D=direct, G=group
