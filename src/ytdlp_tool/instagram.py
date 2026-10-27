"""Instagram post caption (metadata only) and speech-to-text (audio ASR).

Post descriptions and spoken subtitles are distinct. No login/cookie bypass.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlsplit

from .media import MediaError, inspect_media
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
