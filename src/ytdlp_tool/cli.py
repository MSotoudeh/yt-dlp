from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .downloader import SubtitleDownloadError, download_subtitle, inspect_video
from .subtitles import SubtitleUnavailableError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdlp-tool",
        description="Reusable yt-dlp automation toolkit (subtitle capability v1)",
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_subtitles",
        help="List manual and automatic subtitle languages without downloading",
    )
    parser.add_argument(
        "--lang",
        default="auto",
        help="Subtitle language code, or 'auto' (default: auto)",
    )
    parser.add_argument(
        "--format",
        choices=("srt", "vtt", "txt"),
        default="srt",
        dest="output_format",
        help="Output format (default: srt)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for generated subtitle files (default: output)",
    )
    return parser


def _display_languages(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.list_subtitles:
            catalog = inspect_video(args.url)
            print(f"{catalog.title} [{catalog.video_id}]")
            print(f"Manual: {_display_languages(catalog.manual)}")
            print(f"Automatic: {_display_languages(catalog.automatic)}")
            return 0

        result = download_subtitle(
            args.url,
            args.lang,
            args.output_format,
            args.output_dir,
        )
        print(f"Saved: {result.path}")
        print(f"Language: {result.language} ({result.source})")
        return 0
    except (ValueError, SubtitleUnavailableError, SubtitleDownloadError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
