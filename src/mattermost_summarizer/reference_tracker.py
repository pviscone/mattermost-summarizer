"""URL classification and reference extraction for recursive following."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class ReferenceType(Enum):
    """Type of reference found in thread content."""

    MATTERMOST_THREAD = "mattermost_thread"
    LAUNCHPAD_BUG = "launchpad_bug"
    GITHUB_ISSUE = "github_issue"
    GITHUB_PR = "github_pr"
    MATTERMOST_FILE = "mattermost_file"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedUrl:
    """A URL that has been classified by type."""

    url: str
    reference_type: ReferenceType
    agent_type: str
    display_text: str = ""


@dataclass
class ReferenceTracker:
    """Tracks followed references and depth for recursive following."""

    followed_urls: set[str] = field(default_factory=lambda: set())
    current_depth: int = 0
    max_depth: int = 3

    def has_been_followed(self, url: str) -> bool:
        """Check if a URL has already been followed."""
        return url in self.followed_urls

    def mark_followed(self, url: str) -> None:
        """Mark a URL as followed."""
        self.followed_urls.add(url)

    def can_follow_deeper(self) -> bool:
        """Check if we can follow another level of references."""
        return self.current_depth < self.max_depth

    def increment_depth(self) -> None:
        """Increment the depth counter."""
        self.current_depth += 1

    def reset(self) -> None:
        """Reset tracker state for a new summary operation."""
        self.followed_urls.clear()
        self.current_depth = 0


MATTERMOST_THREAD_PATTERNS = [
    re.compile(r"chat\.[^/]+/([^/]+)/pl/([a-zA-Z0-9]+)", re.IGNORECASE),
    re.compile(r"/(?:team|pl)/([a-zA-Z0-9]+)", re.IGNORECASE),
]

LAUNCHPAD_BUG_PATTERNS = [
    re.compile(r"bugs\.launchpad\.net/[^/]+/\+bug/(\d+)", re.IGNORECASE),
    re.compile(r"launchpad\.net/bugs/(\d+)", re.IGNORECASE),
]

GITHUB_ISSUE_PATTERNS = [
    re.compile(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", re.IGNORECASE),
]

GITHUB_PR_PATTERNS = [
    re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", re.IGNORECASE),
]

MATTERMOST_FILE_PATTERNS = [
    re.compile(r"files\.chat\.[^/]+/([a-zA-Z0-9]+)", re.IGNORECASE),
    re.compile(r"/files/([a-zA-Z0-9]+)", re.IGNORECASE),
]


def classify_url(url: str) -> ReferenceType:
    """Classify a URL by its type.

    Args:
        url: The URL to classify

    Returns:
        ReferenceType enum value
    """
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()

    if "bugs.launchpad.net" in netloc and "/+bug/" in path:
        return ReferenceType.LAUNCHPAD_BUG

    if "github.com" in netloc:
        if "/pull/" in path or "/pr/" in path:
            return ReferenceType.GITHUB_PR
        if "/issues/" in path:
            return ReferenceType.GITHUB_ISSUE

    if "chat." in netloc or re.search(r"/(?:team|pl)/[a-zA-Z0-9]+", path):
        if "/files/" in path or "files.chat" in netloc:
            return ReferenceType.MATTERMOST_FILE
        return ReferenceType.MATTERMOST_THREAD

    if "files.chat" in netloc or "/files/" in path:
        return ReferenceType.MATTERMOST_FILE

    return ReferenceType.UNKNOWN


def get_agent_for_reference_type(ref_type: ReferenceType) -> str:
    """Get the sub-agent name for a given reference type.

    Args:
        ref_type: The reference type

    Returns:
        Agent type name string
    """
    if ref_type == ReferenceType.MATTERMOST_THREAD:
        return "thread_fetcher"
    elif ref_type == ReferenceType.LAUNCHPAD_BUG:
        return "bug_researcher"
    elif ref_type in (ReferenceType.GITHUB_ISSUE, ReferenceType.GITHUB_PR):
        return "github_researcher"
    elif ref_type == ReferenceType.MATTERMOST_FILE:
        return "file_fetcher"
    else:
        return "thread_fetcher"


def classify_url_full(url: str) -> ClassifiedUrl:
    """Classify a URL and return full classification info.

    Args:
        url: The URL to classify

    Returns:
        ClassifiedUrl with all details
    """
    ref_type = classify_url(url)
    agent_type = get_agent_for_reference_type(ref_type)
    return ClassifiedUrl(
        url=url,
        reference_type=ref_type,
        agent_type=agent_type,
    )


def extract_urls_from_text(text: str) -> list[str]:
    """Extract all URLs from text content.

    Looks for URLs starting with http:// or https:// or bare domain paths.

    Args:
        text: Text content to search

    Returns:
        List of URLs found
    """
    url_pattern = re.compile(
        r"https?://[^\s<>\"'\)\]]+|[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z0-9][a-zA-Z0-9-]*[^\s<>\"'\)\]]*"
    )
    urls: list[str] = []
    seen: set[str] = set()

    for match in url_pattern.finditer(text):
        url = match.group()
        if url not in seen and len(url) > 10:
            seen.add(url)
            urls.append(url)

    return urls


def classify_urls_in_text(text: str, tracker: ReferenceTracker | None = None) -> list[ClassifiedUrl]:
    """Extract and classify all URLs from text.

    Args:
        text: Text content to search
        tracker: Optional tracker to check if URLs have already been followed

    Returns:
        List of classified URLs
    """
    urls = extract_urls_from_text(text)
    results: list[ClassifiedUrl] = []

    for url in urls:
        classified = classify_url_full(url)
        if tracker and tracker.has_been_followed(url):
            continue
        results.append(classified)

    return results


def build_reference_following_prompt(
    classified_urls: list[ClassifiedUrl],
    tracker: ReferenceTracker,
) -> str:
    """Build a prompt for the orchestrator about found references.

    Args:
        classified_urls: List of classified URLs found in content
        tracker: Reference tracker for depth info

    Returns:
        Formatted prompt string
    """
    if not classified_urls:
        return "No additional references found in the content."

    lines = ["Found the following references in the content:\n"]

    for i, ref in enumerate(classified_urls, 1):
        agent_desc = {
            "thread_fetcher": "Mattermost thread",
            "bug_researcher": "Launchpad bug",
            "github_researcher": "GitHub issue/PR",
            "file_fetcher": "Mattermost file",
        }.get(ref.agent_type, ref.agent_type)

        lines.append(f"{i}. {ref.url} ({agent_desc})")

    lines.append(f"\nCurrent depth: {tracker.current_depth}/{tracker.max_depth}")

    if tracker.can_follow_deeper():
        lines.append("You may delegate to appropriate sub-agents to fetch additional context.")
    else:
        lines.append("Maximum reference depth reached. Do not follow further references.")

    return "\n".join(lines)


__all__ = [
    "ReferenceType",
    "ClassifiedUrl",
    "ReferenceTracker",
    "classify_url",
    "classify_url_full",
    "get_agent_for_reference_type",
    "extract_urls_from_text",
    "classify_urls_in_text",
    "build_reference_following_prompt",
]
