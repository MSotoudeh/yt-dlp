from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .subtitles import (
    select_subtitle,
    validate_youtube_url,
    vtt_to_srt,
    vtt_to_text,
)


class SubtitleDownloadError(RuntimeError):
    """Raised when yt-dlp cannot produce the requested subtitle file."""


@dataclass(frozen=True)
class SubtitleCatalog:
    video_id: str
    title: str
    manual: tuple[str, ...]
    automatic: tuple[str, ...]


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    language: str
    source: str
    output_format: str
    title: str
    video_id: str


def _inspect_options() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "noplaylist": True,
    }


def inspect_video(url: str) -> SubtitleCatalog:
    validate_youtube_url(url)
    try:
        with YoutubeDL(_inspect_options()) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise SubtitleDownloadError(str(exc)) from exc

    return SubtitleCatalog(
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or info.get("id") or "video"),
        manual=tuple(sorted((info.get("subtitles") or {}).keys())),
        automatic=tuple(sorted((info.get("automatic_captions") or {}).keys())),
    )


def _download_options(language: str, source: str, output_dir: Path) -> dict:
    return {
        **_inspect_options(),
        "writesubtitles": source == "manual",
        "writeautomaticsub": source == "automatic",
        "subtitleslangs": [language],
        "subtitlesformat": "vtt",
        "outtmpl": str(output_dir / "%(title)s [%(id)s].%(ext)s"),
    }


def _requested_filepath(info: dict, language: str) -> Path:
    requested = info.get("requested_subtitles") or {}
    subtitle = requested.get(language) or {}
    filepath = subtitle.get("filepath")
    if not filepath:
        raise SubtitleDownloadError(
            f"yt-dlp did not report a downloaded subtitle path for '{language}'"
        )
    path = Path(filepath)
    if not path.exists():
        raise SubtitleDownloadError(f"Downloaded subtitle file does not exist: {path}")
    return path


def download_subtitle(
    url: str,
    language: str = "auto",
    output_format: str = "srt",
    output_dir: str | Path = "output",
) -> DownloadResult:
    output_format = output_format.lower()
    if output_format not in {"vtt", "srt", "txt"}:
        raise ValueError("Output format must be one of: vtt, srt, txt")

    catalog = inspect_video(url)
    selected_language, source = select_subtitle(
        {key: None for key in catalog.manual},
        {key: None for key in catalog.automatic},
        language,
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    try:
        with YoutubeDL(_download_options(selected_language, source, destination)) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise SubtitleDownloadError(str(exc)) from exc

    source_path = _requested_filepath(info, selected_language)
    final_path = source_path
    if output_format == "txt":
        final_path = source_path.with_suffix(".txt")
        final_path.write_text(vtt_to_text(source_path.read_text(encoding="utf-8")), encoding="utf-8")
        source_path.unlink()
    elif output_format == "srt":
        final_path = source_path.with_suffix(".srt")
        final_path.write_text(vtt_to_srt(source_path.read_text(encoding="utf-8")), encoding="utf-8")
        source_path.unlink()

    return DownloadResult(
        path=final_path,
        language=selected_language,
        source=source,
        output_format=output_format,
        title=catalog.title,
        video_id=catalog.video_id,
    )
