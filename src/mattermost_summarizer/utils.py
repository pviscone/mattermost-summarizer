"""Utility functions for mattermost-summarizer."""

import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

from mattermost_summarizer.exceptions import PermalinkError

__all__ = [
    "PermalinkError",
    "check_config_file_permissions",
    "cleanup_external_loggers",
    "parse_channel_url",
    "parse_message_url",
    "parse_permalink",
    "parse_time_point",
    "setup_logging",
]


def check_config_file_permissions(path: Path) -> None:
    """Check config file permissions and emit a warning if world-readable.

    Args:
        path: Path to the config file to check
    """
    try:
        resolved = path.resolve()
        mode = resolved.stat().st_mode
        if mode & 0o077:
            octal_mode = f"{mode & 0o7777:04o}"
            print(
                f"Warning: Config file '{path}' has permissions {octal_mode} — "
                f"consider 'chmod 0600 {path.name}' to restrict access.",
                file=sys.stderr,
            )
    except OSError:
        # File not found already handled upstream in summarize.py.
        # Remaining OSError (e.g., symlink to deleted target, permission denied
        # on resolved path) is swallowed to avoid noisy failures for a
        # non-critical security warning.
        pass


def setup_logging(log_file: str = "mattermost-summarizer.log", verbose: bool = False) -> None:
    """Configure Python and OpenHands loggers to write to file and optionally stderr.

    Args:
        log_file: Path to the log file (default: mattermost-summarizer.log)
        verbose: If True, add StreamHandler for info/warning/error to stderr.
                 Normal mode: all logs → file only (no stderr output).
                 Verbose mode (-v): info, warning, error → stderr + file; debug → file only.
    """
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    while root_logger.handlers:
        root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)

    if verbose:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)

    for logger_name in ("openhands", "LiteLLM", "litellm"):
        logger = logging.getLogger(logger_name)
        while logger.handlers:
            logger.removeHandler(logger.handlers[0])
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if verbose:
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setLevel(logging.INFO)
            stderr_handler.setFormatter(formatter)
            logger.addHandler(stderr_handler)


def cleanup_external_loggers() -> None:
    """Remove StreamHandlers from litellm and openhands loggers.

    Call this after importing litellm/openhands to ensure they don't
    write to stderr.
    """
    import litellm

    litellm.suppress_debug_info = True

    for logger_name in ("LiteLLM", "litellm", "openhands"):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.StreamHandler):
                logger.removeHandler(cast(logging.Handler, handler))
        if not logger.handlers:
            root = logging.getLogger()
            if root.handlers:
                logger.addHandler(root.handlers[0])
            else:
                logger.addHandler(logging.NullHandler())

    logging.getLogger("litellm").setLevel(logging.ERROR)


def parse_permalink(url: str) -> str:
    """Extract the post ID from a Mattermost permalink URL.

    Mattermost permalinks follow the format:
        https://{server}/{team}/pl/{post_id}
        https://{server}/api/v4/posts/{post_id}

    Args:
        url: A Mattermost permalink URL

    Returns:
        The post ID extracted from the URL

    Raises:
        PermalinkError: If the URL is not a valid Mattermost permalink

    Examples:
        >>> parse_permalink("https://chat.canonical.com/canonical/pl/abc123xyz")
        'abc123xyz'
    """
    if not url:
        raise PermalinkError("Empty URL provided")

    # Parse the URL to validate its structure
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise PermalinkError(f"Invalid URL format: {url}")

    # Mattermost permalinks have /pl/{post_id} or /api/v4/posts/{post_id} in the path.
    # The post_id is an alphanumeric string.
    match = re.search(r"/(?:pl|api/v4/posts)/([a-z0-9]+)", url, re.IGNORECASE)

    if not match:
        raise PermalinkError(
            f"Not a valid Mattermost permalink: {url}\n"
            "Expected format: https://{server}/{team}/pl/{post_id} or "
            "https://{server}/api/v4/posts/{post_id}"
        )

    return match.group(1)


def parse_channel_url(url: str) -> tuple[str, str]:
    """Extract the team and channel names from a Mattermost channel URL."""
    if not url:
        raise PermalinkError("Empty URL provided")

    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise PermalinkError(f"Invalid URL format: {url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 3 or path_parts[1].lower() != "channels":
        raise PermalinkError(
            f"Not a valid Mattermost channel URL: {url}\n"
            "Expected format: https://{server}/{team}/channels/{channel}"
        )

    return unquote(path_parts[0]), unquote(path_parts[2])


def parse_message_url(url: str) -> tuple[str, str]:
    """Extract the team and channel name from a Mattermost /messages/ URL."""
    if not url:
        raise PermalinkError("Empty URL provided")

    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise PermalinkError(f"Invalid URL format: {url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 3 or path_parts[1].lower() != "messages":
        raise PermalinkError(
            f"Not a valid Mattermost direct/group message URL: {url}\n"
            "Expected format: https://{server}/{team}/messages/{channel}"
        )

    channel_name = unquote(path_parts[2]).strip()
    if not channel_name:
        raise PermalinkError(f"Not a valid Mattermost direct/group message URL: {url}")

    return unquote(path_parts[0]), channel_name.lstrip("@")


def parse_time_point(value: str) -> datetime:
    """Parse an ISO 8601 time point into a UTC-naive datetime."""
    if not value:
        raise ValueError("Empty time value provided")

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed
