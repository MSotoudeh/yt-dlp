from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .downloader import SubtitleDownloadError, download_subtitle, inspect_video
from .media import (
    MediaError,
    download_audio,
    download_clip,
    download_playlist,
    download_thumbnail,
    download_video,
    get_comments,
    inspect_media,
    inspect_playlist,
    list_formats,
)
from .subtitles import SubtitleUnavailableError
from .transcribe import TranscriptionError, transcribe_media


COMMANDS = {
    "subs", "info", "formats", "video", "audio",
    "thumbnail", "playlist", "clip", "comments", "transcribe",
}


def build_parser() -> argparse.ArgumentParser:
    """Legacy subtitle parser kept for backward compatibility."""
    parser = argparse.ArgumentParser(
        prog="ytdlp-tool",
        description="Reusable yt-dlp automation toolkit",
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--list", action="store_true", dest="list_subtitles",
        help="List manual and automatic subtitle languages without downloading",
    )
    parser.add_argument(
        "--lang", default="auto",
        help="Subtitle language code, or 'auto' (default: auto)",
    )
    parser.add_argument(
        "--format", choices=("srt", "vtt", "txt"), default="srt",
        dest="output_format", help="Output format (default: srt)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Directory for generated subtitle files (default: output)",
    )
    return parser


def _add_output_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Directory for generated files (default: output)",
    )


def build_command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytdlp-tool",
        description="Automation CLI built on yt-dlp",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    subs = sub.add_parser("subs", help="List or download subtitles")
    subs.add_argument("url")
    subs.add_argument("--list", action="store_true", dest="list_subtitles")
    subs.add_argument("--lang", default="auto")
    subs.add_argument("--format", choices=("srt", "vtt", "txt"), default="srt", dest="output_format")
    _add_output_dir(subs)

    info = sub.add_parser("info", help="Print normalized media metadata as JSON")
    info.add_argument("url")

    formats = sub.add_parser("formats", help="List available media formats")
    formats.add_argument("url")

    video = sub.add_parser("video", help="Download video/media")
    video.add_argument("url")
    video.add_argument("--format-selector", default="bv*+ba/b")
    _add_output_dir(video)

    audio = sub.add_parser("audio", help="Extract audio with ffmpeg")
    audio.add_argument("url")
    audio.add_argument("--codec", default="mp3")
    audio.add_argument("--quality", default="192")
    _add_output_dir(audio)

    transcribe = sub.add_parser("transcribe", help="Download audio and transcribe speech to TXT/SRT")
    transcribe.add_argument("source", help="HTTP(S) video URL or existing local media file")
    transcribe.add_argument("--lang", default="auto", help="Language code, or auto detection")
    transcribe.add_argument("--model", default="small", help="Whisper model (default: small)")
    transcribe.add_argument("--model-dir", type=Path, default=None, help="Optional model cache directory")
    transcribe.add_argument("--video", action="store_true", help="Also download original video")
    transcribe.add_argument("--cpu-threads", type=int, default=8)
    _add_output_dir(transcribe)

    thumb = sub.add_parser("thumbnail", help="Download thumbnail only")
    thumb.add_argument("url")
    _add_output_dir(thumb)

    playlist = sub.add_parser("playlist", help="Inspect or download a playlist")
    playlist.add_argument("url")
    playlist.add_argument("--limit", type=int, default=50)
    playlist.add_argument("--download", choices=("video", "audio"))
    _add_output_dir(playlist)

    clip = sub.add_parser("clip", help="Download a time range from media")
    clip.add_argument("url")
    clip.add_argument("start", help="Start timestamp, e.g. 01:30")
    clip.add_argument("end", help="End timestamp, e.g. 02:10")
    clip.add_argument("--format-selector", default="bv*+ba/b")
    _add_output_dir(clip)

    comments = sub.add_parser("comments", help="Fetch comments as JSON")
    comments.add_argument("url")
    comments.add_argument("--limit", type=int, default=100)
    return parser


def _display_languages(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _print_subtitle_catalog(url: str) -> None:
    catalog = inspect_video(url)
    print(f"{catalog.title} [{catalog.video_id}]")
    print(f"Manual: {_display_languages(catalog.manual)}")
    print(f"Automatic: {_display_languages(catalog.automatic)}")


def _print_file_result(result) -> None:
    print(f"Saved: {result.path}")
    print(f"Type: {result.kind}")


def _run_legacy(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if args.list_subtitles:
        _print_subtitle_catalog(args.url)
        return 0
    result = download_subtitle(
        args.url, args.lang, args.output_format, args.output_dir,
    )
    print(f"Saved: {result.path}")
    print(f"Language: {result.language} ({result.source})")
    return 0


def _run_command(argv: list[str]) -> int:
    args = build_command_parser().parse_args(argv)

    if args.command == "subs":
        if args.list_subtitles:
            _print_subtitle_catalog(args.url)
            return 0
        result = download_subtitle(
            args.url, args.lang, args.output_format, args.output_dir,
        )
        print(f"Saved: {result.path}")
        print(f"Language: {result.language} ({result.source})")
        return 0

    if args.command == "info":
        print(json.dumps(asdict(inspect_media(args.url)), ensure_ascii=True, indent=2))
        return 0

    if args.command == "formats":
        for item in list_formats(args.url):
            size = item.filesize if item.filesize is not None else "-"
            print("\t".join([
                item.format_id,
                item.ext or "-",
                item.resolution or "-",
                item.vcodec or "-",
                item.acodec or "-",
                str(size),
            ]))
        return 0

    if args.command == "video":
        _print_file_result(download_video(args.url, args.output_dir, args.format_selector))
        return 0

    if args.command == "audio":
        _print_file_result(download_audio(
            args.url, args.output_dir, args.codec, args.quality,
        ))
        return 0

    if args.command == "transcribe":
        result = transcribe_media(
            args.source, args.output_dir, args.lang, args.model,
            model_dir=args.model_dir, download_original_video=args.video,
            cpu_threads=args.cpu_threads,
        )
        print(f"Text: {result.txt_path}")
        print(f"Subtitles: {result.srt_path}")
        print(f"Audio: {result.audio_path}")
        if result.video_path:
            print(f"Video: {result.video_path}")
        print(f"Language: {result.language}")
        print(f"Segments: {result.segments}")
        return 0

    if args.command == "thumbnail":
        _print_file_result(download_thumbnail(args.url, args.output_dir))
        return 0

    if args.command == "playlist":
        if args.download:
            result = download_playlist(
                args.url, args.output_dir, args.download, args.limit,
            )
            print(f"{result.title} [{result.playlist_id}]")
            print(f"Saved files: {len(result.paths)}")
            for path in result.paths:
                print(path)
            return 0
        playlist = inspect_playlist(args.url, args.limit)
        print(f"{playlist.title} [{playlist.playlist_id}]")
        if playlist.uploader:
            print(f"Uploader: {playlist.uploader}")
        for index, entry in enumerate(playlist.entries, 1):
            print(f"{index}\t{entry.video_id}\t{entry.title}\t{entry.url or '-'}")
        return 0

    if args.command == "clip":
        _print_file_result(download_clip(
            args.url, args.start, args.end,
            args.output_dir, args.format_selector,
        ))
        return 0

    if args.command == "comments":
        comments = get_comments(args.url, args.limit)
        print(json.dumps(list(comments), ensure_ascii=True, indent=2))
        return 0

    raise ValueError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    try:
        if not values or values[0] in COMMANDS or values[0] in {"-h", "--help"}:
            return _run_command(values)
        return _run_legacy(values)
    except (
        ValueError,
        MediaError,
        TranscriptionError,
        SubtitleUnavailableError,
        SubtitleDownloadError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
