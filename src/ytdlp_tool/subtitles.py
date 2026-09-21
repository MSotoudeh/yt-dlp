from __future__ import annotations

from html import unescape
import re
from urllib.parse import urlparse


class SubtitleUnavailableError(LookupError):
    """Raised when the requested subtitle language is not available."""


def validate_youtube_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use http or https")

    host = (parsed.hostname or "").lower()
    valid_host = (
        host == "youtu.be"
        or host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtube-nocookie.com"
        or host.endswith(".youtube-nocookie.com")
    )
    if not valid_host:
        raise ValueError("Only YouTube URLs are supported")
    return True


def _english_key(mapping: dict) -> str | None:
    for key in mapping:
        if key == "en" or key.startswith("en-") or key.startswith("en."):
            return key
    return None


def _matching_key(mapping: dict, requested: str) -> str | None:
    if requested in mapping:
        return requested
    for key in mapping:
        if key.startswith(f"{requested}-") or key.startswith(f"{requested}."):
            return key
    return None


def select_subtitle(manual: dict, automatic: dict, requested: str) -> tuple[str, str]:
    if requested != "auto":
        manual_key = _matching_key(manual, requested)
        if manual_key:
            return manual_key, "manual"
        automatic_key = _matching_key(automatic, requested)
        if automatic_key:
            return automatic_key, "automatic"
        raise SubtitleUnavailableError(f"Subtitle language '{requested}' is unavailable")

    manual_en = _english_key(manual)
    if manual_en:
        return manual_en, "manual"
    if manual:
        return sorted(manual)[0], "manual"
    automatic_en = _english_key(automatic)
    if automatic_en:
        return automatic_en, "automatic"
    if automatic:
        return sorted(automatic)[0], "automatic"
    raise SubtitleUnavailableError("This video has no subtitles")


_TIMESTAMP = re.compile(r"^\s*(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3}\s+-->\s+")
_TAG = re.compile(r"<[^>]+>")
_INLINE_TIMESTAMP = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")


def vtt_to_text(content: str) -> str:
    lines: list[str] = []
    previous = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if _TIMESTAMP.match(line) or line.isdigit():
            continue
        line = _INLINE_TIMESTAMP.sub("", line)
        line = unescape(_TAG.sub("", line)).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines) + ("\n" if lines else "")
