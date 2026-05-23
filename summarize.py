#!/usr/bin/env python3
"""CLI script to summarize a Mattermost thread."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
from pathlib import Path

logging.getLogger("litellm").setLevel(logging.ERROR)
os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:5000"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = (
    "x-mlflow-experiment-id=0"  # Replace "123" with your MLflow experiment ID
)
os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/protobuf"

def main() -> int:
    from mattermost_summarizer.utils import cleanup_external_loggers, setup_logging

    setup_logging()

    from mattermost_summarizer.config import MattermostSummarizerConfig
    from mattermost_summarizer.levels import SummaryLevel
    from mattermost_summarizer.summarizer import MattermostSummarizer

    cleanup_external_loggers()

    parser = argparse.ArgumentParser(description="Summarize a Mattermost thread")
    parser.add_argument(
        "url",
        help="Mattermost thread URL (e.g., https://chat.canonical.com/canonical/pl/post_id)",
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

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        config = MattermostSummarizerConfig.from_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    level = config.summarizer_default_level
    if args.level is not None:
        level = SummaryLevel(args.level)

    try:
        summarizer = MattermostSummarizer(config)
        with contextlib.redirect_stdout(sys.stderr):
            result = summarizer.summarize(args.url, level=level)
    except Exception as e:
        print(f"Error summarizing thread: {e}", file=sys.stderr)
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
