"""Digital Concert Hall downloads with a short-lived browser access token.

The site no longer supports username/password login, so yt-dlp's official extractor needs the
``access_token_production`` value from the user's own signed-in browser. This module keeps that
token as safe as a CLI can:

* it is read from a hidden prompt or from stdin, never from argv or an environment variable;
* it lives only in this process's memory (yt-dlp's token cache is disabled with ``cachedir=False``);
* it is checked for expiry before any network call, and scrubbed from every error message.

Only content the signed-in account may already stream is requested. DRM or access errors are
reported as such; nothing here tries to get around them.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


class DchError(RuntimeError):
    """A Digital Concert Hall request could not be completed."""


DCH_HOSTS = {"digitalconcerthall.com", "www.digitalconcerthall.com"}
_PATH = re.compile(r"^/(?P<lang>[a-z]{2,3})/(?P<kind>film|concert|work)/(?P<id>[0-9]+)(?:-(?P<part>[0-9]+))?/?$")
DEFAULT_FORMAT = "bv*+ba/b"
TOKEN_HINT = (
    'Copy a fresh "access_token_production" from the signed-in site (browser DevTools > Application > '
    "Local Storage) and run the command again."
)


@dataclass(frozen=True)
class DchItem:
    index: int
    video_id: str
    title: str
    duration: float | None
    formats: int
    best_height: int | None


@dataclass(frozen=True)
class DchDownload:
    paths: tuple[Path, ...]
    items: int


def validate_dch_url(url: str) -> str:
    """Return the URL if it is an https Digital Concert Hall film/concert/work page."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise ValueError("Not a valid URL") from exc
    if parts.scheme != "https" or parts.hostname not in DCH_HOSTS or port not in (None, 443):
        raise ValueError("URL must be https://www.digitalconcerthall.com/...")
    if parts.username or parts.password:
        raise ValueError("URL must not contain credentials")
    if not _PATH.match(parts.path):
        raise ValueError(
            "Expected a page like https://www.digitalconcerthall.com/en/concert/56205 "
            "(film, concert or work)"
        )
    return f"https://{parts.hostname}{parts.path.rstrip('/')}"


def token_seconds_left(token: str, now: float | None = None) -> int | None:
    """Seconds until the JWT expires, or None if it carries no expiry. Raises if malformed/expired.

    The signature is not verified (the server does that); this only avoids a doomed request.
    """
    pieces = token.split(".")
    if len(pieces) != 3:
        raise DchError("That does not look like an access token (expected a JWT). " + TOKEN_HINT)
    try:
        payload = json.loads(base64.urlsafe_b64decode(pieces[1] + "=" * (-len(pieces[1]) % 4)))
    except (ValueError, UnicodeDecodeError) as exc:
        raise DchError("That does not look like an access token (unreadable payload). " + TOKEN_HINT) from exc
    exp = payload.get("exp") if isinstance(payload, dict) else None
    if not isinstance(exp, (int, float)):
        return None
    left = int(exp - (time.time() if now is None else now))
    if left <= 30:
        raise DchError("The access token has expired. " + TOKEN_HINT)
    return left


def _scrub(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _options(token: str, extra: dict | None = None) -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": False,
        "username": "token",
        "password": token,
        "cachedir": False,  # the extractor would otherwise write the token to disk
        **(extra or {}),
    }


def _extract(url: str, token: str, extra: dict | None, *, download: bool) -> dict:
    try:
        with YoutubeDL(_options(token, extra)) as ydl:
            info = ydl.extract_info(url, download=download)
    except DownloadError as exc:
        message = _scrub(str(exc), token)
        lowered = message.lower()
        if "drm" in lowered:
            raise DchError("This stream is DRM-protected and cannot be downloaded: " + message[-200:]) from None
        if any(w in lowered for w in ("token", "401", "login", "expired", "invalid")):
            hint = "" if "access_token_production" in message else " " + TOKEN_HINT
            raise DchError("Digital Concert Hall rejected the token: " + message[-300:] + hint) from None
        raise DchError(message[-300:]) from None
    if not info:
        raise DchError("Digital Concert Hall returned no information for this page")
    return info


def _entries(info: dict) -> list[dict]:
    return [e for e in (info.get("entries") or ()) if e] or ([info] if info.get("formats") else [])


def list_items(url: str, token: str) -> tuple[DchItem, ...]:
    """Metadata and format counts per item; nothing is downloaded."""
    url = validate_dch_url(url)
    token_seconds_left(token)
    items = []
    for index, entry in enumerate(_entries(_extract(url, token, {"skip_download": True}, download=False)), 1):
        formats = entry.get("formats") or ()
        heights = [f["height"] for f in formats if isinstance(f.get("height"), int)]
        items.append(DchItem(
            index=index,
            video_id=str(entry.get("id") or ""),
            title=str(entry.get("title") or entry.get("id") or "item"),
            duration=entry.get("duration"),
            formats=len(formats),
            best_height=max(heights) if heights else None,
        ))
    return tuple(items)


def _snapshot(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {p.resolve() for p in directory.rglob("*") if p.is_file()}


def download(
    url: str,
    token: str,
    output_dir: str | Path = "output/digital-concert-hall",
    *,
    item: int | None = None,
    format_selector: str = DEFAULT_FORMAT,
) -> DchDownload:
    """Download all items of the page (or only ``item``, 1-based) and return the finished files."""
    url = validate_dch_url(url)
    if item is not None and item < 1:
        raise ValueError("--item must be 1 or greater")
    if not shutil.which("ffmpeg"):
        raise DchError("ffmpeg is required to merge the streams; install it and add it to PATH")
    token_seconds_left(token)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    before = _snapshot(destination)
    extra = {
        "format": format_selector,
        "outtmpl": str(destination / "%(playlist_title)s [%(playlist_id)s]"
                       / "%(playlist_index)02d - %(title)s [%(id)s].%(ext)s"),
        "overwrites": False,
    }
    if item is not None:
        extra["playlist_items"] = str(item)
    info = _extract(url, token, extra, download=True)
    created = sorted(
        p for p in _snapshot(destination) - before
        if p.suffix.lower() not in {".part", ".ytdl", ".temp"} and p.stat().st_size > 0
    )
    if not created:
        raise DchError(
            "yt-dlp finished but no new media file was found (already downloaded, or nothing was available)"
        )
    return DchDownload(paths=tuple(created), items=len(_entries(info)))
