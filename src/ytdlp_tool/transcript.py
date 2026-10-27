"""Prefer YouTube's published transcript tracks; use local ASR only when absent."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .downloader import download_subtitle
from .subtitles import SubtitleUnavailableError, validate_youtube_url
from .transcribe import transcribe_media


@dataclass(frozen=True)
class PreferredTranscript:
    paths: tuple[Path, ...]
    source: str
    language: str


def get_preferred_transcript(
    url: str,
    output_dir: str | Path = "output",
    language: str = "auto",
    model: str = "small",
    *,
    model_dir: str | Path | None = None,
    cpu_threads: int = 8,
    output_format: str | None = None,
) -> PreferredTranscript:
    """Use a published YouTube caption track before downloading or decoding audio.

    Only a genuinely missing/empty caption track triggers ASR. Access errors,
    rate limits and broken downloads remain visible, not silently reclassified.
    """
    validate_youtube_url(url)
    if output_format is not None and output_format not in {"txt", "srt"}:
        raise ValueError("Output format must be txt or srt")
    root = Path(output_dir)
    try:
        caption = download_subtitle(url, language, output_format or "txt", root / "captions")
        if not caption.path.read_text(encoding="utf-8").strip():
            caption.path.unlink(missing_ok=True)
            raise SubtitleUnavailableError("YouTube returned an empty transcript")
        return PreferredTranscript(
            paths=(caption.path,),
            source="youtube_" + caption.source,
            language=caption.language,
        )
    except SubtitleUnavailableError:
        recognized = transcribe_media(
            url, root, language, model,
            model_dir=model_dir, cpu_threads=cpu_threads,
        )
        return PreferredTranscript(
            paths=((recognized.txt_path, recognized.srt_path) if output_format is None
                   else (recognized.txt_path if output_format == "txt" else recognized.srt_path,)),
            source="asr",
            language=recognized.language,
        )
