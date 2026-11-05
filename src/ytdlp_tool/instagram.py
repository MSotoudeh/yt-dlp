"""Instagram post caption (metadata only) and speech-to-text (audio ASR).

Post descriptions and spoken subtitles are distinct. No login/cookie bypass.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from .media import MediaError, inspect_media, download_video
from .transcribe import transcribe_media


INSTAGRAM_HOSTS = frozenset({
    "instagram.com", "www.instagram.com", "m.instagram.com",
})
_MEDIA_PATH = re.compile(r"^/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)(?:/)?$")


def validate_instagram_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in INSTAGRAM_HOSTS:
        raise ValueError("Expected a public Instagram post or Reel HTTPS URL")
    if parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValueError("Invalid Instagram URL")
    match = _MEDIA_PATH.fullmatch(parsed.path)
    if not match:
        raise ValueError("Use an Instagram post or Reel URL (/p/ or /reel/)")
    return match.group(1)


@dataclass(frozen=True)
class InstagramTextResult:
    path: Path
    source: str
    language: str | None


def extract_post_caption(url: str, output_dir: str | Path = "output") -> InstagramTextResult:
    """Get the author's written caption, not speech or burned-in overlay text."""
    shortcode = validate_instagram_url(url)
    info = inspect_media(url)
    caption = info.description
    if not isinstance(caption, str) or not caption.strip():
        raise MediaError("Instagram post caption is absent or inaccessible; no text was invented")
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"instagram-{shortcode}-caption.txt"
    path.write_text(caption.strip() + "\n", encoding="utf-8")
    return InstagramTextResult(path, "instagram_post_caption", None)


def extract_spoken_text(
    url: str,
    output_dir: str | Path = "output",
    output_format: str = "txt",
    *,
    model: str = "large-v3",
    model_dir: str | Path | None = None,
    cpu_threads: int = 8,
) -> InstagramTextResult:
    """Produce transcript of actual spoken audio; ASR timings yield SRT."""
    validate_instagram_url(url)
    if output_format not in ("txt", "srt"):
        raise ValueError("Instagram speech format must be txt or srt")
    recognized = transcribe_media(
        url, output_dir, language="auto", model=model, model_dir=model_dir,
        cpu_threads=cpu_threads,
    )
    path = recognized.txt_path if output_format == "txt" else recognized.srt_path
    return InstagramTextResult(path, "asr", recognized.language)


MEDIA_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm"})


def _download_gallery_media(url: str, destination: Path) -> tuple[Path, ...]:
    """Download public gallery media without loading user configs or browser cookies."""
    gallery = destination / "gallery"
    gallery.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "gallery_dl", "--config-ignore",
        "--directory", str(gallery),
        "--range", "1-20", "--filesize-max", "49M", url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise MediaError(f"Instagram gallery retrieval failed: {exc}") from exc
    files = sorted(
        (p for p in gallery.rglob("*")
         if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS),
        key=lambda p: p.name,
    )
    if result.returncode or not files:
        problem = (result.stderr or result.stdout or "no accessible media").strip()
        raise MediaError(f"Instagram gallery retrieval unavailable: {problem[-350:]}")
    return tuple(files)


def download_instagram_media(
    url: str,
    output_dir: str | Path = "output",
) -> tuple[Path, ...]:
    """Download accessible Reel video or public post media, without authentication bypass."""
    validate_instagram_url(url)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if urlsplit(url).path.startswith(("/reel/", "/reels/", "/tv/")):
        return (download_video(url, output / "video").path,)

    try:
        return _download_gallery_media(url, output)
    except MediaError as gallery_error:
        # Video-only Instagram /p/ URLs can be handled by yt-dlp, even when
        # gallery-dl cannot access the gallery endpoint.
        try:
            result = download_video(url, output / "video")
            video_files = sorted(
                (p for p in (output / "video").rglob("*")
                 if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS),
                key=lambda p: p.name,
            )
            return tuple(video_files) or (result.path,)
        except MediaError as video_error:
            raise MediaError(
                f"Instagram photo/album not accessible without authorized login; "
                f"gallery: {gallery_error}; video: {video_error}"
            ) from video_error
