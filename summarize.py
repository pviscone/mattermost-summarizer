#!/usr/bin/env python3
"""CLI script to summarize a Mattermost thread."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

logging.getLogger("litellm").setLevel(logging.ERROR)
os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")


# Patch OTel context propagation into DelegateExecutor threads so that
# sub-agent spans nest correctly under their parent DelegateAction span.
from mattermost_summarizer.tracing_patch import install as _install_tracing_patch  # noqa: E402

_install_tracing_patch()


def main() -> int:
    from mattermost_summarizer.utils import cleanup_external_loggers, setup_logging

    parser = argparse.ArgumentParser(description="Summarize a Mattermost thread")
    parser.add_argument(
        "url",
        help="Mattermost thread URL, or a Mattermost channel URL when using --start_time and --end_time",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="mattermost-summarizer.toml",
        help="Path to TOML config file (default: mattermost-summarizer.toml)",
    )
    parser.add_argument(
        "--output",
        "-o",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--level",
        "-l",
        choices=["brief", "normal", "detailed"],
        default=None,
        help="Summarization level (overrides config default_level)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (info/warning/error to stderr)",
    )
    parser.add_argument(
        "--prompt",
        "-p",
        default=None,
        help="Custom prompt to append to the default model prompt",
    )
    parser.add_argument("--start_time", default=None, help="Start time for filtering posts (ISO 8601)")
    parser.add_argument("--end_time", default=None, help="End time for filtering posts (ISO 8601)")

    args = parser.parse_args()

    # Support using the literal value "present" to indicate the current time.
    # Example: --start_time 2026-01-01T00:00:00 --end_time present
    if args.end_time is not None and isinstance(args.end_time, str) and args.end_time.lower() == "present":
        args.end_time = datetime.now(timezone.utc).isoformat()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 1

    from mattermost_summarizer.config import MattermostSummarizerConfig
    from mattermost_summarizer.utils import check_config_file_permissions

    check_config_file_permissions(config_path)

    try:
        config = MattermostSummarizerConfig.from_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    verbose = args.verbose or config.verbose or os.environ.get("MM_VERBOSE", "").lower() in ("1", "true", "yes")
    setup_logging(verbose=verbose)

    cleanup_external_loggers()

    from mattermost_summarizer.levels import SummaryLevel
    from mattermost_summarizer.summarizer import MattermostSummarizer

    level = config.summarizer_default_level
    if args.level is not None:
        level = SummaryLevel(args.level)

    try:
        summarizer = MattermostSummarizer(config)
        with contextlib.redirect_stdout(sys.stderr):
            result = summarizer.summarize(
                args.url,
                level=level,
                prompt=args.prompt,
                start_time=args.start_time,
                end_time=args.end_time,
            )
    except Exception as e:
        print(f"Error summarizing thread ({type(e).__name__}): {e}", file=sys.stderr)
        return 1

    if args.output == "json":
        print(result.model_dump_json(indent=2))
    elif sys.stdout.isatty():
        from rich.console import Console

        console = Console()
        result.render_rich(console)
    else:
        print(str(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
