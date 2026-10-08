"""Offline regression tests for the optional Whisper integration."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import ytdlp_tool.cli as cli
import ytdlp_tool.transcribe as asr
from ytdlp_tool.media import FileResult


def fake_whisper(monkeypatch, segments=None, language="fa"):
    calls = []
    class FakeModel:
        def __init__(self, *args, **kwargs):
            calls.append((args, kwargs))
        def transcribe(self, audio, **kwargs):
            calls.append((audio, kwargs))
            data = segments if segments is not None else [
                SimpleNamespace(start=0.0, end=2.5, text="سلام دنیا"),
                SimpleNamespace(start=2.5, end=63.125, text="این یک آزمایش است"),
            ]
            return iter(data), SimpleNamespace(language=language)
    monkeypatch.setitem(sys.modules, "faster_whisper",
                        SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(asr, "_decode_pcm", lambda path: "fake pcm")
    return calls


def test_local_transcription_writes_bom_txt_and_valid_srt(tmp_path, monkeypatch):
    media = tmp_path / "persian audio.mp3"
    media.write_bytes(b"mp3")
    calls = fake_whisper(monkeypatch)
    result = asr.transcribe_media(str(media), tmp_path / "results",
                                  model_dir=tmp_path / "cache")
    assert result.audio_path == media.resolve()
    assert result.video_path is None
    assert result.language == "fa"
    assert result.segments == 2
    assert result.txt_path.read_text(encoding="utf-8-sig") == (
        "سلام دنیا\nاین یک آزمایش است\n")
    assert "00:00:02,500 --> 00:01:03,125" in result.srt_path.read_text(
        encoding="utf-8-sig")
    assert result.txt_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert calls[0][0] == ("small",)
    assert calls[1][1]["language"] is None


def test_url_downloads_audio_and_optional_video(tmp_path, monkeypatch):
    calls = fake_whisper(monkeypatch, language="en")
    fake_audio = tmp_path / "clip.mp3"
    fake_video = tmp_path / "clip.mp4"
    fake_audio.write_bytes(b"audio")
    fake_video.write_bytes(b"video")
    downloads = []
    def audio(url, directory):
        downloads.append(("audio", url, directory))
        return FileResult(fake_audio, "clip", "abc", "audio")
    def video(url, directory):
        downloads.append(("video", url, directory))
        return FileResult(fake_video, "clip", "abc", "video")
    monkeypatch.setattr(asr, "download_audio", audio)
    monkeypatch.setattr(asr, "download_video", video)
    result = asr.transcribe_media("https://example.com/watch", tmp_path / "out",
                                  "en", "base", download_original_video=True)
    assert result.video_path == fake_video
    assert result.audio_path == fake_audio
    assert [item[0] for item in downloads] == ["audio", "video"]
    assert downloads[0][2] == tmp_path / "out" / "audio"
    assert calls[1][1]["language"] == "en"


def test_invalid_source_and_options_do_not_download(tmp_path):
    with pytest.raises(ValueError, match="URL"):
        asr.transcribe_media("not-a-file", tmp_path)
    with pytest.raises(ValueError, match="positive"):
        asr.transcribe_media("https://example.com/a", tmp_path, cpu_threads=0)


def test_no_speech_never_creates_transcript(tmp_path, monkeypatch):
    media = tmp_path / "empty.wav"
    media.write_bytes(b"empty")
    fake_whisper(monkeypatch, segments=[])
    with pytest.raises(asr.TranscriptionError, match="No speech"):
        asr.transcribe_media(str(media), tmp_path / "out")
    assert not (tmp_path / "out" / "transcripts").exists()


def test_ffmpeg_required(tmp_path, monkeypatch):
    monkeypatch.setattr(asr.shutil, "which", lambda executable: None)
    with pytest.raises(asr.TranscriptionError, match="ffmpeg"):
        asr._decode_pcm(tmp_path / "fake.mp3")


def test_cli_dispatch_with_flags(tmp_path, monkeypatch, capsys):
    captured = {}
    def fake(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return asr.TranscriptResult(
            tmp_path / "speech.txt", tmp_path / "speech.srt",
            tmp_path / "sound.mp3", None, "fa", 2,
        )
    monkeypatch.setattr(cli, "transcribe_media", fake)
    assert cli.main(["transcribe", "https://example.com/a", "--lang", "fa",
                     "--model", "base", "--cpu-threads", "2",
                     "--output-dir", str(tmp_path)]) == 0
    assert captured["args"] == ("https://example.com/a", Path(tmp_path), "fa", "base")
    assert captured["kwargs"]["cpu_threads"] == 2
    assert "Segments: 2" in capsys.readouterr().out


def test_cli_recovers_from_asr_error(tmp_path, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise asr.TranscriptionError("model download failed")
    monkeypatch.setattr(cli, "transcribe_media", fail)
    assert cli.main(["transcribe", "https://example.com/a"]) == 1
    assert "model download failed" in capsys.readouterr().err
