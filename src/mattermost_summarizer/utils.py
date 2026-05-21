"""Utility functions for mattermost-summarizer."""

import logging
import re
from urllib.parse import urlparse

from mattermost_summarizer.exceptions import PermalinkError

__all__ = ["PermalinkError", "cleanup_external_loggers", "parse_permalink", "setup_logging"]


def setup_logging(log_file: str = "mattermost-summarizer.log") -> None:
    """Configure Python and OpenHands loggers to write exclusively to a file.

    Removes any default StreamHandler from stdout/stderr and redirects all
    logging to a FileHandler.

    Args:
        log_file: Path to the log file (default: mattermost-summarizer.log)
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

    for logger_name in ("openhands", "LiteLLM", "litellm"):
        logger = logging.getLogger(logger_name)
        while logger.handlers:
            logger.removeHandler(logger.handlers[0])
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False


def cleanup_external_loggers() -> None:
    """Remove StreamHandlers from litellm and openhands loggers.

    Call this after importing litellm/openhands to ensure they don't
    write to stderr.
    """
    for logger_name in ("LiteLLM", "litellm", "openhands"):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.StreamHandler):
                logger.removeHandler(handler)  # type: ignore[reportUnknownArgumentType]
        if not logger.handlers:
            root = logging.getLogger()
            if root.handlers:
                logger.addHandler(root.handlers[0])
            else:
                logger.addHandler(logging.NullHandler())


def parse_permalink(url: str) -> str:
    """Extract the post ID from a Mattermost permalink URL.

    Mattermost permalinks follow the format:
        https://{server}/{team}/pl/{post_id}

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

    # Mattermost permalinks have /pl/{post_id} in the path
    # The post_id is a alphanumeric string
    match = re.search(r"/pl/([a-z0-9]+)", url, re.IGNORECASE)

    if not match:
        raise PermalinkError(
            f"Not a valid Mattermost permalink: {url}\n"
            "Expected format: https://{{server}}/{{team}}/pl/{{post_id}}"
        )

    return match.group(1)
