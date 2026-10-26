from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, download_range_func


class MediaError(RuntimeError):
    """Raised when yt-dlp cannot complete a media operation."""


@dataclass(frozen=True)
class MediaInfo:
    video_id: str
    title: str
    uploader: str | None
    duration: float | None
    webpage_url: str | None
    description: str | None
    thumbnail: str | None


@dataclass(frozen=True)
class FormatInfo:
    format_id: str
    ext: str | None
    resolution: str | None
    vcodec: str | None
    acodec: str | None
    filesize: int | None


@dataclass(frozen=True)
class FileResult:
    path: Path
    title: str
    video_id: str
    kind: str


@dataclass(frozen=True)
class PlaylistEntry:
    video_id: str
    title: str
    url: str | None


@dataclass(frozen=True)
class PlaylistInfo:
    playlist_id: str
    title: str
    uploader: str | None
    entries: tuple[PlaylistEntry, ...]


@dataclass(frozen=True)
class PlaylistDownloadResult:
    playlist_id: str
    title: str
    mode: str
    paths: tuple[Path, ...]


def validate_media_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http or https URL")


def _base_options(*, noplaylist: bool = True) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": noplaylist,
    }


def _extract(url: str, options: dict | None = None, *, download: bool = False) -> dict:
    validate_media_url(url)
    merged = {**_base_options(), **(options or {})}
    try:
        with YoutubeDL(merged) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as exc:
        raise MediaError(str(exc)) from exc


def _media_info(info: dict) -> MediaInfo:
    return MediaInfo(
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or info.get("id") or "media"),
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        webpage_url=info.get("webpage_url") or info.get("original_url"),
        description=info.get("description"),
        thumbnail=info.get("thumbnail"),
    )


def inspect_media(url: str) -> MediaInfo:
    return _media_info(_extract(url, {"skip_download": True}, download=False))


def list_formats(url: str) -> tuple[FormatInfo, ...]:
    info = _extract(url, {"skip_download": True}, download=False)
    results: list[FormatInfo] = []
    for item in info.get("formats") or ():
        width, height = item.get("width"), item.get("height")
        resolution = item.get("resolution") or (
            f"{width}x{height}" if width and height else item.get("format_note")
        )
        results.append(FormatInfo(
            format_id=str(item.get("format_id") or ""),
            ext=item.get("ext"),
            resolution=resolution,
            vcodec=item.get("vcodec"),
            acodec=item.get("acodec"),
            filesize=item.get("filesize") or item.get("filesize_approx"),
        ))
    return tuple(results)


def _snapshot(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path.resolve() for path in directory.rglob("*") if path.is_file()}


def _result_path(directory: Path, before: set[Path], info: dict) -> Path:
    created = _snapshot(directory) - before
    if created:
        return max(created, key=lambda path: path.stat().st_mtime_ns)
    for item in info.get("requested_downloads") or ():
        if item.get("filepath") and Path(item["filepath"]).exists():
            return Path(item["filepath"])
    filename = info.get("_filename")
    if filename and Path(filename).exists():
        return Path(filename)
    raise MediaError("yt-dlp completed but no output file could be located")


def _download_file(url: str, destination: Path, options: dict, kind: str) -> FileResult:
    destination.mkdir(parents=True, exist_ok=True)
    before = _snapshot(destination)
    info = _extract(url, options, download=True)
    path = _result_path(destination, before, info)
    core = _media_info(info)
    return FileResult(path, core.title, core.video_id, kind)


def download_video(
    url: str,
    output_dir: str | Path = "output",
    format_selector: str = "bv*+ba/b",
) -> FileResult:
    destination = Path(output_dir)
    return _download_file(url, destination, {
        "format": format_selector,
        "outtmpl": str(destination / "%(title)s [%(id)s].%(ext)s"),
    }, "video")


def download_audio(
    url: str,
    output_dir: str | Path = "output",
    codec: str = "mp3",
    quality: str = "192",
) -> FileResult:
    destination = Path(output_dir)
    return _download_file(url, destination, {
        "format": "ba/b",
        "outtmpl": str(destination / "%(title)s [%(id)s].%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": codec,
            "preferredquality": quality,
        }],
    }, "audio")


def download_thumbnail(url: str, output_dir: str | Path = "output") -> FileResult:
    destination = Path(output_dir)
    return _download_file(url, destination, {
        "skip_download": True,
        "writethumbnail": True,
        "outtmpl": str(destination / "%(title)s [%(id)s].%(ext)s"),
    }, "thumbnail")


def get_comments(url: str, limit: int = 100) -> tuple[dict, ...]:
    if limit < 1:
        raise ValueError("Comment limit must be at least 1")
    info = _extract(url, {
        "skip_download": True,
        "getcomments": True,
        "extractor_args": {
            "youtube": {"max_comments": [str(limit)]},
        },
    }, download=False)
    return tuple((info.get("comments") or ())[:limit])


def inspect_playlist(url: str, limit: int = 50) -> PlaylistInfo:
    if limit < 1:
        raise ValueError("Playlist limit must be at least 1")
    info = _extract(url, {
        "skip_download": True,
        "noplaylist": False,
        "extract_flat": "in_playlist",
        "playlistend": limit,
    }, download=False)
    entries = tuple(
        PlaylistEntry(
            str(item.get("id") or ""),
            str(item.get("title") or item.get("id") or "media"),
            item.get("webpage_url") or item.get("url"),
        )
        for item in (info.get("entries") or ()) if item
    )
    return PlaylistInfo(
        playlist_id=str(info.get("id") or ""),
        title=str(info.get("title") or info.get("id") or "playlist"),
        uploader=info.get("uploader") or info.get("channel"),
        entries=entries,
    )


def download_playlist(
    url: str,
    output_dir: str | Path = "output",
    mode: str = "video",
    limit: int = 50,
) -> PlaylistDownloadResult:
    if mode not in {"video", "audio"}:
        raise ValueError("Playlist mode must be 'video' or 'audio'")
    if limit < 1:
        raise ValueError("Playlist limit must be at least 1")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    before = _snapshot(destination)
    options = {
        "noplaylist": False,
        "playlistend": limit,
        "outtmpl": str(destination / "%(playlist_title)s" /
                       "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"),
    }
    if mode == "audio":
        options.update({
            "format": "ba/b",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        })
    info = _extract(url, options, download=True)
    paths = tuple(sorted(_snapshot(destination) - before))
    if not paths:
        raise MediaError("Playlist download completed but no output files were located")
    return PlaylistDownloadResult(
        playlist_id=str(info.get("id") or ""),
        title=str(info.get("title") or info.get("id") or "playlist"),
        mode=mode,
        paths=paths,
    )


def parse_timestamp(value: str) -> float:
    try:
        if ":" not in value:
            seconds = float(value)
        else:
            parts = [float(part) for part in value.split(":")]
            if len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            else:
                raise ValueError
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc
    if seconds < 0:
        raise ValueError("Timestamp cannot be negative")
    return seconds


def download_clip(
    url: str,
    start: str,
    end: str,
    output_dir: str | Path = "output",
    format_selector: str = "bv*+ba/b",
) -> FileResult:
    start_seconds = parse_timestamp(start)
    end_seconds = parse_timestamp(end)
    if end_seconds <= start_seconds:
        raise ValueError("Clip end must be after clip start")
    destination = Path(output_dir)
    return _download_file(url, destination, {
        "format": format_selector,
        "download_ranges": download_range_func(None, [(start_seconds, end_seconds)]),
        "force_keyframes_at_cuts": True,
        "outtmpl": str(destination / (
            "%(title)s [%(id)s] " + f"[{start}-{end}].%(ext)s"
        )),
    }, "clip")
