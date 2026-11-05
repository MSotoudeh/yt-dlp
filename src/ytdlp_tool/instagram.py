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
    if urlsplit(url).path.startswith("/p/"):
        try:
            _, post = _load_instaloader_post(shortcode)
            caption = post.caption
        except MediaError:
            # Public video posts may still work through yt-dlp.
            caption = inspect_media(url).description
    else:
        caption = inspect_media(url).description
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
        return _download_instaloader_media(url, output)
    except MediaError as instaloader_exc:
        instaloader_error = str(instaloader_exc)
        # Preserve the existing fallback if Instagram's public metadata endpoint
        # temporarily stops serving this specific post.
        try:
            return _download_gallery_media(url, output)
        except MediaError as gallery_exc:
            gallery_error = str(gallery_exc)
    try:
        return _fallback_video_post(url, output)
    except MediaError as video_error:
        raise MediaError(
            f"Instagram post unavailable anonymously: {instaloader_error}; "
            f"gallery: {gallery_error}; video: {video_error}"
        ) from video_error


def _fallback_video_post(url: str, output: Path) -> tuple[Path, ...]:
    """Fetch video-only /p/ media with yt-dlp if other public paths fail."""
    result = download_video(url, output / "video")
    video_files = sorted(
        (p for p in (output / "video").rglob("*")
         if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS),
        key=lambda p: p.name,
    )
    return tuple(video_files) or (result.path,)





def _load_instaloader_post(shortcode: str):
    """Fetch public Instagram metadata anonymously, without loading a login session."""
    try:
        import instaloader
    except ImportError as exc:
        raise MediaError("Instaloader dependency missing: install ytdlp-tool[instagram]") from exc
    try:
        loader = instaloader.Instaloader(
            quiet=True, save_metadata=False, download_pictures=False,
            download_videos=False, download_video_thumbnails=False,
        )
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        return loader.context, post
    except instaloader.exceptions.InstaloaderException as exc:
        raise MediaError(f"Instagram public metadata unavailable: {exc}") from exc


def _trusted_instagram_media_url(url: str) -> bool:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and parsed.port in (None, 443)
        and parsed.username is None and parsed.password is None
        and (
            host.endswith(".cdninstagram.com") or host.endswith(".fbcdn.net")
        )
    )


def _download_instaloader_media(url: str, destination: Path) -> tuple[Path, ...]:
    """Download each real public post image/video in carousel order."""
    shortcode = validate_instagram_url(url)
    context, post = _load_instaloader_post(shortcode)
    nodes = list(post.get_sidecar_nodes()) if post.typename == "GraphSidecar" else [post]
    if not nodes or len(nodes) > 20:
        raise MediaError("Instagram album is empty or contains more than 20 items")
    folder = destination / "instaloader"
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, node in enumerate(nodes, 1):
        is_video = bool(node.is_video)
        source = (
            node.video_url if is_video else
            getattr(node, "display_url", None) or getattr(node, "url", None)
        )
        if not source or not _trusted_instagram_media_url(source):
            raise MediaError("Instagram CDN media URL missing or untrusted")
        try:
            response = context.get_raw(source)
        except Exception as exc:
            raise MediaError(
                f"Instagram public media could not be retrieved: {type(exc).__name__}"
            ) from exc
        if response.status_code != 200 or not _trusted_instagram_media_url(response.url):
            raise MediaError("Instagram CDN media response is unavailable or redirected")
        payload = response.content
        max_size = (49 if is_video else 10) * 1024 * 1024
        if not payload or len(payload) > max_size:
            raise MediaError("Instagram media empty or too large for Telegram")
        if not is_video and not payload.startswith(bytes((0xFF, 0xD8, 0xFF))):
            raise MediaError("Instagram image response is not a valid JPEG")
        if is_video and payload[4:8] != b"ftyp":
            raise MediaError("Instagram media response is not a valid MP4")
        suffix = ".mp4" if is_video else ".jpg"
        path = folder / f"{index:02d}{suffix}"
        path.write_bytes(payload)
        paths.append(path)
    return tuple(paths)
