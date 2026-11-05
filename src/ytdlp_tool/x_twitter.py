"""Public X/Twitter status retrieval: original text and attached media only.

Uses X's public embedded-tweet syndication JSON. No paid API, user cookies,
login, unofficial guest tokens, image OCR, or speech recognition.
This endpoint is undocumented and availability can change.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import re

import requests

from .media import MediaError


X_HOSTS = frozenset({
    "x.com", "www.x.com", "mobile.x.com",
    "twitter.com", "www.twitter.com", "mobile.twitter.com",
})
_PATH = re.compile(
    r"^/(?:[A-Za-z0-9_]{1,30}|i/web)/status/([0-9]{1,22})"
    r"(?:/(?:photo|video)/[1-9][0-9]?)?/?$"
)
_USER_AGENT = "Mozilla/5.0 (compatible; YTDL-Private-Telegram-Bot/1.0)"
_SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result"
_CHUNK = 128 * 1024


class XError(MediaError):
    """Public post or media unavailable."""


@dataclass(frozen=True)
class XMedia:
    kind: str  # photo, video
    urls: tuple[str, ...]  # highest bitrate first, alternatives for video


@dataclass(frozen=True)
class XPost:
    status_id: str
    text: str
    media: tuple[XMedia, ...]


@dataclass(frozen=True)
class XDownload:
    text: str
    text_path: Path
    media: tuple[Path, ...]
    warnings: tuple[str, ...]


def validate_status_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in X_HOSTS
                or parts.port not in (None, 443)
                or parts.username or parts.password):
            raise ValueError("Expected an HTTPS public X/Twitter status URL")
        matched = _PATH.fullmatch(parts.path)
        if not matched or int(matched.group(1)) <= 0:
            raise ValueError("Expected /USERNAME/status/TWEET_ID URL")
        return matched.group(1)
    except (TypeError, AttributeError) as exc:
        raise ValueError("Invalid X/Twitter status URL") from exc


def _media_from_payload(data: dict) -> tuple[XMedia, ...]:
    items: list[XMedia] = []
    seen: set[str] = set()
    details = data.get("mediaDetails") or []
    if not isinstance(details, list):
        details = []
    for entry in details:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("type")
        if kind == "photo":
            src = entry.get("media_url_https")
            candidates = (src,) if isinstance(src, str) and src else ()
            item_kind = "photo"
        elif kind in ("video", "animated_gif"):
            variants = (entry.get("video_info") or {}).get("variants") or []
            variants = [
                v for v in variants
                if isinstance(v, dict) and v.get("content_type") == "video/mp4"
                and isinstance(v.get("url"), str)
            ]
            variants.sort(key=lambda v: v.get("bitrate") or 0, reverse=True)
            candidates = tuple(v["url"] for v in variants)
            item_kind = "video"
        else:
            continue
        if candidates and candidates[0] not in seen:
            items.append(XMedia(item_kind, tuple(candidates)))
            seen.add(candidates[0])
    if not items:
        # Embedded tweet JSON sometimes includes photos/video but no mediaDetails.
        for photo in data.get("photos") or []:
            if not isinstance(photo, dict):
                continue
            src = photo.get("url")
            if isinstance(src, str) and src and src not in seen:
                items.append(XMedia("photo", (src,)))
                seen.add(src)
        video = data.get("video") or {}
        if isinstance(video, dict):
            sources = [
                v.get("src") for v in video.get("variants") or []
                if isinstance(v, dict) and v.get("type") == "video/mp4"
                and isinstance(v.get("src"), str)
            ]
            if sources and sources[0] not in seen:
                items.append(XMedia("video", tuple(sources)))
    return tuple(items[:10])


def fetch_post(url: str) -> XPost:
    status_id = validate_status_url(url)
    try:
        response = requests.get(
            _SYNDICATION,
            params={"id": status_id, "lang": "en", "token": "0"},
            timeout=(10, 20),
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise XError(f"X public syndication unavailable (HTTP {response.status_code})")
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise XError(f"Unable to retrieve public X status: {type(exc).__name__}") from exc
    if (not isinstance(payload, dict)
            or payload.get("__typename") not in (None, "Tweet")
            or str(payload.get("id_str", status_id)) != status_id):
        raise XError("X post is unavailable, protected, or deleted")
    raw_text = payload.get("text")
    note = payload.get("note_tweet") or {}
    if isinstance(note, dict) and isinstance(note.get("text"), str):
        raw_text = note["text"]
    if not isinstance(raw_text, str):
        raise XError("X post is unavailable, protected, or deleted")
    return XPost(status_id, raw_text, _media_from_payload(payload))


def _trusted_media_url(url: str, kind: str) -> bool:
    try:
        parsed = urlsplit(url)
        valid_host = {"pbs.twimg.com"} if kind == "photo" else {
            "video.twimg.com", "pbs.twimg.com"
        }
        return (
            parsed.scheme == "https"
            and parsed.hostname in valid_host
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
        )
    except ValueError:
        return False


def _download_one(item: XMedia, destination: Path) -> Path:
    limit = (10 if item.kind == "photo" else 49) * 1024 * 1024
    errors = []
    for source in item.urls:
        if not _trusted_media_url(source, item.kind):
            errors.append("untrusted X media CDN address")
            continue
        try:
            with requests.get(
                source, stream=True, timeout=(10, 45), allow_redirects=False,
                headers={"User-Agent": _USER_AGENT},
            ) as response:
                if response.status_code != 200:
                    raise XError(f"X media HTTP {response.status_code}")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > limit:
                    raise XError("X media larger than Telegram upload limit")
                buffer = bytearray()
                for chunk in response.iter_content(chunk_size=_CHUNK):
                    if not chunk:
                        continue
                    buffer.extend(chunk)
                    if len(buffer) > limit:
                        raise XError("X media larger than Telegram upload limit")
                data = bytes(buffer)
            if item.kind == "photo":
                if data.startswith(bytes((0xFF, 0xD8, 0xFF))):
                    extension = ".jpg"
                elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                    extension = ".png"
                else:
                    raise XError("X image format unsupported (JPEG/PNG only)")
            elif len(data) >= 8 and data[4:8] == b"ftyp":
                extension = ".mp4"
            else:
                raise XError("X video is not a valid MP4")
            result = destination.with_suffix(extension)
            result.parent.mkdir(parents=True, exist_ok=True)
            result.write_bytes(data)
            return result
        except (requests.RequestException, OSError, ValueError, XError) as exc:
            errors.append(str(exc)[:100])
    raise XError("X media unavailable: " + ("; ".join(errors[-2:]) or "no sources"))


def download_post(url: str, output_dir: str | Path = "output") -> XDownload:
    post = fetch_post(url)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    text_file = output / f"tweet-{post.status_id}.txt"
    text_file.write_text(post.text, encoding="utf-8")
    media: list[Path] = []
    warnings: list[str] = []
    for index, item in enumerate(post.media, start=1):
        try:
            media.append(_download_one(item, output / f"{index:02d}"))
        except XError as exc:
            warnings.append(f"media {index} unavailable: {exc}")
    return XDownload(post.text, text_file, tuple(media), tuple(warnings))
