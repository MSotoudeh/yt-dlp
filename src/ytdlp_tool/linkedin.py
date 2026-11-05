"""Public LinkedIn single-post text and attached media, without account credentials.

Reads the public LinkedIn post Embed view (the user's post ID is the only
variable in the fetched URL). Not an official API. No browser session/cookies,
site protection bypass, content inference, OCR, or speech transcription.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

import requests

from .media import MediaError

_POST_ID = re.compile(r"^[1-9][0-9]{12,21}$")
_POSTS_PATH = re.compile(
    r"^/posts/[A-Za-z0-9_%\-]{1,230}-(?:activity|ugcpost|share)-([0-9]{13,22})"
    r"-[A-Za-z0-9_-]{1,20}/?$",
    re.I,
)
_FEED_PATH = re.compile(
    r"^/(?:embed/)?feed/update/urn:li:(?:activity|ugcPost|share):([0-9]{13,22})/?$",
    re.I,
)
_MEDIA_HOSTS = {"media.licdn.com", "dms.licdn.com"}
_LIMIT = 49 * 1024 * 1024
_IMAGE_LIMIT = 10 * 1024 * 1024
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
_CHUNK = 128 * 1024


class LinkedInError(MediaError):
    """Post or media is not publicly accessible."""


@dataclass(frozen=True)
class LinkedInMedia:
    kind: str
    urls: tuple[str, ...]


@dataclass(frozen=True)
class LinkedInPost:
    post_id: str
    text: str
    media: tuple[LinkedInMedia, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class LinkedInDownload:
    text: str
    text_path: Path
    media: tuple[Path, ...]
    warnings: tuple[str, ...]


def validate_post_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        match_host = (host == "linkedin.com" or host == "www.linkedin.com"
                      or bool(re.fullmatch(r"[a-z]{2,3}\.linkedin\.com", host)))
        if (parsed.scheme != "https" or not match_host
                or parsed.port not in (None, 443) or parsed.username
                or parsed.password or parsed.fragment):
            raise ValueError("Expected public HTTPS LinkedIn post URL")
        match = _POSTS_PATH.fullmatch(parsed.path) or _FEED_PATH.fullmatch(parsed.path)
        if not match or not _POST_ID.fullmatch(match.group(1)):
            raise ValueError("Expected LinkedIn /posts/ or /feed/update/ activity link")
        return match.group(1)
    except (AttributeError, TypeError) as exc:
        raise ValueError("Invalid LinkedIn URL") from exc


class _EmbeddedPostParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urns: list[str] = []
        self._text_active = False
        self._text_parts: list[str] = []
        self._gallery_active = False
        self._overlay_active = False
        self._overlay_parts: list[str] = []
        self._video_sources: list[dict] = []
        self._gallery_urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        marker = d.get("data-test-id") or ""
        if tag == "article":
            urn = d.get("data-activity-urn") or ""
            self.urns.append(urn)
        elif tag == "p" and marker == "main-feed-activity-embed-card__commentary":
            self._text_active = True
        elif tag == "ul" and marker == "feed-images-content":
            self._gallery_active = True
        elif tag == "img" and self._gallery_active:
            src = d.get("data-delayed-url") or ""
            if src and src not in self._gallery_urls:
                self._gallery_urls.append(src)
        elif tag == "div" and marker == "feed-images-content__overlay":
            self._overlay_active = True
        elif tag == "video" and "share-native-video__node" in (d.get("class") or ""):
            try:
                val = json.loads(d.get("data-sources") or "[]")
                if isinstance(val, list):
                    self._video_sources.extend(v for v in val if isinstance(v, dict))
            except (ValueError, TypeError):
                pass

    def handle_endtag(self, tag):
        if tag == "p":
            self._text_active = False
        elif tag == "ul":
            self._gallery_active = False
        elif tag == "div":
            self._overlay_active = False

    def handle_data(self, data):
        if self._text_active:
            self._text_parts.append(data)
        if self._overlay_active:
            self._overlay_parts.append(data)

    def result(self, post_id: str) -> LinkedInPost:
        expected = "urn:li:activity:" + post_id
        if not any(u.endswith(":" + post_id) for u in self.urns):
            raise LinkedInError("LinkedIn public post unavailable or activity mismatch")
        text = "".join(self._text_parts).strip()
        media: list[LinkedInMedia] = [
            LinkedInMedia("photo", (src,)) for src in self._gallery_urls[:20]
        ]
        variants = [
            entry for entry in self._video_sources
            if entry.get("type") == "video/mp4"
            and isinstance(entry.get("src"), str)
        ]
        variants.sort(key=lambda v: int(v.get("data-bitrate") or 0), reverse=True)
        if variants:
            media.append(LinkedInMedia("video", tuple(v["src"] for v in variants)))
        warning: list[str] = []
        total_hidden = sum(
            int(v) for v in re.findall(r"\+([0-9]{1,2})", "".join(self._overlay_parts))
        )
        if total_hidden:
            warning.append(
                f"Public LinkedIn embed hides {total_hidden} additional photo(s); "
                "only its displayed images are retrievable anonymously"
            )
        if not text and not media:
            raise LinkedInError("No original text or media accessible in public LinkedIn embed")
        return LinkedInPost(post_id, text, tuple(media), tuple(warning))


def parse_embed(source: str, post_id: str) -> LinkedInPost:
    p = _EmbeddedPostParser()
    p.feed(source)
    return p.result(post_id)


def fetch_post(url: str) -> LinkedInPost:
    post_id = validate_post_url(url)
    resource = f"https://www.linkedin.com/embed/feed/update/urn:li:activity:{post_id}"
    try:
        result = requests.get(
            resource, headers=_HEADERS, timeout=(8, 25), allow_redirects=False
        )
    except requests.RequestException as exc:
        raise LinkedInError(f"Public LinkedIn embed could not be fetched: {type(exc).__name__}") from exc
    if result.status_code != 200:
        raise LinkedInError(
            f"Public LinkedIn embed returned HTTP {result.status_code}; login or restriction may apply"
        )
    if len(result.content) > 3 * 1024 * 1024:
        raise LinkedInError("LinkedIn embed page too large")
    return parse_embed(result.text, post_id)


def _trusted_cdn(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname in _MEDIA_HOSTS
                and parsed.port in (None, 443) and not parsed.username and not parsed.password)
    except ValueError:
        return False


def _download_media(media: LinkedInMedia, target: Path) -> Path:
    # Some LinkedIn "photo" attachments are large animated GIFs.
    # Allow up to 49 MiB for inspection; still enforce photo limit for JPEG/PNG.
    max_len = _LIMIT
    errors: list[str] = []
    for source in media.urls:
        if not _trusted_cdn(source):
            errors.append("untrusted LinkedIn CDN")
            continue
        try:
            with requests.get(
                source, headers=_HEADERS, stream=True,
                timeout=(8, 45), allow_redirects=False
            ) as resp:
                if resp.status_code != 200:
                    raise LinkedInError(f"LinkedIn media unavailable (HTTP {resp.status_code})")
                announced = resp.headers.get("content-length")
                if announced and int(announced) > max_len:
                    raise LinkedInError("LinkedIn media exceeds Telegram direct upload limit")
                buf = bytearray()
                for part in resp.iter_content(chunk_size=_CHUNK):
                    if not part:
                        continue
                    buf.extend(part)
                    if len(buf) > max_len:
                        raise LinkedInError("LinkedIn media exceeds Telegram direct upload limit")
            raw = bytes(buf)
            if media.kind == "photo":
                if raw.startswith(bytes((0xFF, 0xD8, 0xFF))):
                    ext = ".jpg"
                elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    ext = ".png"
                elif raw.startswith((b"GIF87a", b"GIF89a")):
                    ext = ".gif"
                else:
                    raise LinkedInError("Unsupported LinkedIn photo format (JPEG/PNG/GIF required)")
                if ext != ".gif" and len(raw) > _IMAGE_LIMIT:
                    raise LinkedInError("LinkedIn photo exceeds Telegram photo size limit")
            elif len(raw) >= 8 and raw[4:8] == b"ftyp":
                ext = ".mp4"
            else:
                raise LinkedInError("Unsupported LinkedIn video format (MP4 required)")
            path = target.with_suffix(ext)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return path
        except (requests.RequestException, LinkedInError, OSError, ValueError) as exc:
            errors.append(str(exc)[:120])
    raise LinkedInError("LinkedIn media unavailable: " + ("; ".join(errors[-2:]) or "no sources"))


def download_post(url: str, output_dir: str | Path = "output") -> LinkedInDownload:
    post = fetch_post(url)
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    text_file = folder / f"linkedin-{post.post_id}.txt"
    text_file.write_text(post.text, encoding="utf-8")
    media_files: list[Path] = []
    warnings = list(post.warnings)
    for index, asset in enumerate(post.media, 1):
        try:
            media_files.append(_download_media(asset, folder / f"{index:02d}"))
        except LinkedInError as exc:
            warnings.append(f"media {index} unavailable: {exc}")
    return LinkedInDownload(post.text, text_file, tuple(media_files), tuple(warnings))
