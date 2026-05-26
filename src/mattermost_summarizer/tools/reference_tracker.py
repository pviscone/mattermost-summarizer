"""URL classification and reference extraction for recursive following."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

from mattermost_summarizer.ssrf import check_url_ssrf


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
    """Tracks followed references and depth for recursive following.

    Depth is tracked per-URL rather than globally.  Siblings discovered in the
    same References block share the same depth level, so ``max_depth=3`` allows
    e.g. 6 sibling URLs at depth 1 each surfacing sub-references at depth 2.

    Lifecycle per URL:
      1. ``register_pending(url, depth)``  — called at injection time for each
         URL surfaced by a sub-agent, before the orchestrator sees the block.
      2. ``get_depth_for(url)``            — called by the executor just before
         delegating; returns the pre-registered depth (or ``None`` for root).
      3. ``mark_followed(url, depth)``     — called after delegation completes;
         moves the URL from ``pending_urls`` into ``followed_urls``.

    All public methods are individually thread-safe.  Use the :meth:`lock`
    context manager for compound check-then-act operations.
    """

    followed_urls: dict[str, int] = field(default_factory=lambda: {})
    pending_urls: dict[str, int] = field(default_factory=lambda: {})
    max_depth: int = 3
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False, compare=False)

    @contextmanager
    def lock(self) -> Generator[None, None, None]:
        """Context manager that holds the internal lock for compound operations."""
        with self._lock:
            yield

    def has_been_followed(self, url: str) -> bool:
        """Check if a URL has already been followed."""
        with self._lock:
            return url in self.followed_urls

    def register_pending(self, url: str, depth: int) -> None:
        """Register a URL as pending with its expected fetch depth.

        Called at injection time (when building the References block) for each
        followable URL discovered in a sub-agent result.
        """
        with self._lock:
            self.pending_urls[url] = depth

    def get_depth_for(self, url: str) -> int | None:
        """Return the depth assigned to *url*, or ``None`` if unregistered (root).

        Checks ``pending_urls`` first (not yet fetched), then ``followed_urls``
        (already fetched — useful for trace introspection).
        """
        with self._lock:
            if url in self.pending_urls:
                return self.pending_urls[url]
            if url in self.followed_urls:
                return self.followed_urls[url]
            return None

    def mark_followed(self, url: str, depth: int) -> None:
        """Mark a URL as followed at *depth*, removing it from pending."""
        with self._lock:
            self.pending_urls.pop(url, None)
            self.followed_urls[url] = depth

    def reset(self) -> None:
        """Reset tracker state for a new summary operation."""
        with self._lock:
            self.followed_urls.clear()
            self.pending_urls.clear()


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


def sanitize_url(url: str) -> str:
    """Sanitize a URL to avoid parser errors.

    Replaces bracketed IPv6 literals (e.g. http://[fd00::1]/path) with a
    placeholder so downstream URL parsers don't raise "Invalid IPv6 URL".
    Also strips bare ``[`` that lack a closing ``]`` in the authority
    section (before the first ``/``, ``?``, or ``#``) — these can be
    caused by ``extract_urls_from_text`` truncating at ``]``.

    Args:
        url: Raw URL string

    Returns:
        Sanitized URL safe for urlparse
    """
    url = re.sub(r"\[([0-9a-fA-F:]+)\]", "ipv6-placeholder", url)
    m = re.match(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^/?#]*)(.*)", url)
    if m:
        scheme_and_authority = m.group(1).replace("[", "")
        url = scheme_and_authority + m.group(2)
    # Strip a trailing ] only when it has no matching [ in the URL —
    # these arise from malformed markdown like [text](https://example.com]).
    if url.endswith("]") and url.count("[") < url.count("]"):
        url = url[:-1]
    return url


def classify_url(url: str) -> ReferenceType:
    """Classify a URL by its type.

    Args:
        url: The URL to classify

    Returns:
        ReferenceType enum value
    """
    ssrf_result = check_url_ssrf(url)
    if not ssrf_result.is_safe:
        logging.getLogger(__name__).warning(
            "SSRF check blocked URL: %s (%s)",
            url,
            ssrf_result.reason,
        )
        return ReferenceType.UNKNOWN

    parsed = urlparse(sanitize_url(url))
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
        raise ValueError(f"No sub-agent defined for reference type: {ref_type}")


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
    url_pattern = re.compile(r"https?://[^\s<>\"'\)]+|[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z0-9][a-zA-Z0-9-]*[^\s<>\"'\)]*")
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
        if tracker and tracker.has_been_followed(url):
            continue
        try:
            classified = classify_url_full(url)
            if classified.reference_type != ReferenceType.UNKNOWN:
                results.append(classified)
        except ValueError as e:
            logging.getLogger(__name__).warning("Skipping unparseable URL: %s  reason=%s", url, e)

    return results


def build_reference_following_prompt(
    classified_urls: list[ClassifiedUrl],
    tracker: ReferenceTracker,
    parent_depth: int = 0,
    context_sentences: dict[str, str] | None = None,
) -> str:
    """Build a prompt for the orchestrator about found references.

    Args:
        classified_urls: List of classified URLs found in content
        tracker: Reference tracker for depth info
        parent_depth: The depth at which the parent was fetched (child URLs
            will be at parent_depth + 1)
        context_sentences: Optional mapping of url → one-sentence description
            extracted from the sub-agent result text

    Returns:
        Formatted prompt string
    """
    if not classified_urls:
        return "No additional references found in the content."

    child_depth = parent_depth + 1
    context_sentences = context_sentences or {}

    lines = ["Found the following references in the content:\n"]

    for i, ref in enumerate(classified_urls, 1):
        agent_desc = {
            "thread_fetcher": "Mattermost thread",
            "bug_researcher": "Launchpad bug",
            "github_researcher": "GitHub issue/PR",
            "file_fetcher": "Mattermost file",
        }.get(ref.agent_type, ref.agent_type)

        ctx = context_sentences.get(ref.url, "")
        if ctx:
            lines.append(f"{i}. {ref.url} ({agent_desc}) — {ctx}")
        else:
            lines.append(f"{i}. {ref.url} ({agent_desc})")

    if child_depth < tracker.max_depth:
        lines.append(f"\nDepth: {child_depth}/{tracker.max_depth}")
        lines.append("You may call fetch_reference on the above URLs to fetch additional context.")
    else:
        lines.append(
            f"\nDepth: {child_depth}/{tracker.max_depth}"
            " — Maximum reference depth reached. Do not follow further references."
        )

    return "\n".join(lines)


def extract_sentence_context(text: str, url: str) -> str:
    """Extract a one-sentence description surrounding *url* from *text*.

    Strategy (in priority order):
    1. If the URL is in the middle of a sentence — return that sentence.
    2. If the URL starts a sentence — return that sentence.
    3. If the URL is on its own line and the previous line has text — return
       the previous line (treated as a description heading).
    4. Fallback — return ``"(no description available)"`` if no sentence
       boundary is found within 300 characters of the URL.

    The returned string has the URL itself stripped out to avoid duplication
    in the References block.
    """
    url_pos = text.find(url)
    if url_pos == -1:
        return "(no description available)"

    # Sentence-ending characters
    sent_end = re.compile(r"[.!?]\s")

    window_start = max(0, url_pos - 300)
    window_end = min(len(text), url_pos + len(url) + 300)
    window = text[window_start:window_end]
    url_in_window = url_pos - window_start

    # Find the sentence that contains the URL within the window
    # Walk backwards from url_pos to find sentence start
    before = window[:url_in_window]
    after = window[url_in_window + len(url) :]

    # Find start of current sentence (last .  !  ? in `before`)
    sent_start_match = None
    for m in sent_end.finditer(before):
        sent_start_match = m
    if sent_start_match:
        sent_start_pos = sent_start_match.end()
    else:
        # No sentence boundary before URL — use start of current line
        line_start = before.rfind("\n")
        sent_start_pos = line_start + 1 if line_start != -1 else 0

    # Find end of current sentence (first .  !  ? in `after`)
    sent_end_match = sent_end.search(after)
    if sent_end_match:
        sent_end_in_after = sent_end_match.end()
    else:
        # No sentence boundary after URL — try newline
        nl = after.find("\n")
        sent_end_in_after = nl if nl != -1 else len(after)

    sentence = before[sent_start_pos:] + url + after[:sent_end_in_after]
    sentence = sentence.strip()

    # If the extracted sentence is just the URL itself or very short,
    # try the previous line as a description
    stripped = sentence.replace(url, "").strip().rstrip(".!?,;:")
    if len(stripped) < 5:
        prev_line_end = before.rfind("\n")
        if prev_line_end != -1:
            prev_line_start = before.rfind("\n", 0, prev_line_end)
            prev_line = before[prev_line_start + 1 : prev_line_end].strip()
            if len(prev_line) >= 5:
                return prev_line
        return "(no description available)"

    # Strip the URL from the returned context to avoid duplication
    result = sentence.replace(url, "").strip().rstrip(".!?,;:").strip()
    if len(result) < 5:
        return "(no description available)"
    return result


__all__ = [
    "ReferenceType",
    "ClassifiedUrl",
    "ReferenceTracker",
    "sanitize_url",
    "classify_url",
    "classify_url_full",
    "get_agent_for_reference_type",
    "extract_urls_from_text",
    "classify_urls_in_text",
    "build_reference_following_prompt",
    "extract_sentence_context",
]
