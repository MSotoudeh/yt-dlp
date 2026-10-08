"""Transcribe an online video or local media file to UTF-8 text and SRT.

Whisper is an optional dependency; base yt-dlp installs remain lightweight.
Audio decoding uses ffmpeg PCM rather than PyAV so Windows/Python 3.14
environments do not depend on particular PyAV keyword compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from .media import download_audio, download_video, validate_media_url


class TranscriptionError(RuntimeError):
    """A transcription prerequisite or processing stage failed."""


@dataclass(frozen=True)
class TranscriptResult:
    txt_path: Path
    srt_path: Path
    audio_path: Path
    video_path: Path | None
    language: str
    segments: int


def _timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _decode_pcm(path: Path):
    """Decode media once into mono, 16kHz float32 for Whisper."""
    if not shutil.which("ffmpeg"):
        raise TranscriptionError("ffmpeg is required; install it and add it to PATH")
    try:
        import numpy as np
    except ImportError as exc:
        raise TranscriptionError(
            "Missing ASR dependencies. Install with: python -m pip install -e '.[asr]'"
        ) from exc
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-ac", "1", "-ar", "16000",
        "-f", "f32le", "pipe:1",
    ]
    proc = subprocess.run(command, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise TranscriptionError(f"Audio decode failed: {detail or 'no audio samples'}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def transcribe_media(
    source: str,
    output_dir: str | Path = "output",
    language: str = "auto",
    model: str = "small",
    *,
    model_dir: str | Path | None = None,
    download_original_video: bool = False,
    cpu_threads: int = 8,
) -> TranscriptResult:
    """Download audio for HTTP(S) sources and write TXT/SRT from speech.

    Local media paths bypass network downloads. Files are written only after
    transcription succeeds, avoiding truncated "successful" results.
    """
    if cpu_threads < 1:
        raise ValueError("cpu_threads must be positive")
    if not language or not model:
        raise ValueError("language and model cannot be empty")
    source_path = Path(source).expanduser()
    local_file = source_path.is_file()
    if not local_file:
        validate_media_url(source)
    if local_file and download_original_video:
        raise ValueError("--video applies only to HTTP(S) sources")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "Missing faster-whisper. Install with: python -m pip install -e '.[asr]'"
        ) from exc

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if local_file:
        audio_path = source_path.resolve()
        video_path = None
    else:
        audio_path = download_audio(source, root / "audio").path
        video_path = (
            download_video(source, root / "video").path
            if download_original_video else None
        )
    pcm = _decode_pcm(audio_path)
    cache = Path(model_dir) if model_dir else Path("output") / "asr-models"
    try:
        whisper = WhisperModel(
            model, device="cpu", compute_type="int8",
            cpu_threads=cpu_threads, download_root=str(cache),
        )
        segments, info = whisper.transcribe(
            pcm, language=None if language == "auto" else language,
            beam_size=5, vad_filter=True, condition_on_previous_text=False,
        )
        captions = [
            (segment.start, segment.end, segment.text.strip())
            for segment in segments if segment.text.strip()
        ]
    except Exception as exc:
        raise TranscriptionError(f"Whisper transcription failed: {exc}") from exc

    if not captions:
        raise TranscriptionError("No speech detected; no transcript created")

    directory = root / "transcripts"
    directory.mkdir(parents=True, exist_ok=True)
    txt_path = directory / (audio_path.stem + ".txt")
    srt_path = directory / (audio_path.stem + ".srt")
    txt = "\n".join(text for _, _, text in captions) + "\n"
    srt = "\n".join(
        f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(captions, 1)
    )
    txt_path.write_text(txt, encoding="utf-8-sig")
    srt_path.write_text(srt, encoding="utf-8-sig")
    return TranscriptResult(
        txt_path, srt_path, audio_path, video_path,
        getattr(info, "language", language), len(captions),
    )
