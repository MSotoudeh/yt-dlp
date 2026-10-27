from pathlib import Path

import pytest

import ytdlp_tool.transcript as transcript
from ytdlp_tool.downloader import DownloadResult, SubtitleDownloadError
from ytdlp_tool.subtitles import SubtitleUnavailableError
from ytdlp_tool.transcribe import TranscriptResult


URL = "https://youtu.be/abc123"


def test_published_manual_caption_skips_all_asr(monkeypatch, tmp_path):
    text = tmp_path / "manual.txt"
    text.write_text("Accurate original words.\n", encoding="utf-8")
    calls = []

    def fake_subs(url, lang, fmt, directory):
        calls.append(("subs", lang, fmt))
        return DownloadResult(text, "fa", "manual", "txt", "demo", "abc123")

    def never_asr(*args, **kwargs):
        pytest.fail("ASR must not run when YouTube captions exist")

    monkeypatch.setattr(transcript, "download_subtitle", fake_subs)
    monkeypatch.setattr(transcript, "transcribe_media", never_asr)
    result = transcript.get_preferred_transcript(URL, tmp_path, model="large-v3")
    assert calls == [("subs", "auto", "txt")]
    assert result.paths == (text,)
    assert result.source == "youtube_manual"
    assert result.language == "fa"


def test_published_auto_caption_skips_all_asr(monkeypatch, tmp_path):
    text = tmp_path / "automatic.txt"
    text.write_text("Caption text.\n", encoding="utf-8")
    monkeypatch.setattr(
        transcript, "download_subtitle",
        lambda *a: DownloadResult(text, "fa", "automatic", "txt", "demo", "abc123"),
    )
    monkeypatch.setattr(
        transcript, "transcribe_media",
        lambda *a, **kw: pytest.fail("ASR not expected"),
    )
    result = transcript.get_preferred_transcript(URL, tmp_path)
    assert result.source == "youtube_automatic"


@pytest.mark.parametrize("caption_state", ["missing", "empty"])
def test_asr_only_when_captions_absent_or_empty(monkeypatch, tmp_path, caption_state):
    def fake_subs(*args):
        if caption_state == "missing":
            raise SubtitleUnavailableError("No caption track")
        text = tmp_path / "empty.txt"
        text.write_text("  \n", encoding="utf-8")
        return DownloadResult(text, "en", "manual", "txt", "demo", "abc123")

    calls = []
    def fake_asr(url, output_dir, language, model, **kwargs):
        calls.append((url, language, model, kwargs["model_dir"]))
        return TranscriptResult(tmp_path / "speech.txt", tmp_path / "speech.srt",
                                tmp_path / "audio.mp3", None, "fa", 3)

    monkeypatch.setattr(transcript, "download_subtitle", fake_subs)
    monkeypatch.setattr(transcript, "transcribe_media", fake_asr)
    result = transcript.get_preferred_transcript(
        URL, tmp_path, model="large-v3", model_dir=tmp_path / "models",
    )
    assert result.source == "asr"
    assert len(result.paths) == 2
    assert calls == [(URL, "auto", "large-v3", tmp_path / "models")]


def test_caption_download_failure_not_mistaken_for_missing_subtitles(monkeypatch, tmp_path):
    def fail(*args):
        raise SubtitleDownloadError("HTTP 403: authentication required")

    monkeypatch.setattr(transcript, "download_subtitle", fail)
    monkeypatch.setattr(transcript, "transcribe_media",
                        lambda *a, **kw: pytest.fail("Do not retry protected media via ASR"))
    with pytest.raises(SubtitleDownloadError, match="403"):
        transcript.get_preferred_transcript(URL, tmp_path)


def test_non_youtube_is_rejected_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(transcript, "download_subtitle", lambda *a: pytest.fail("no network"))
    with pytest.raises(ValueError, match="Only YouTube"):
        transcript.get_preferred_transcript("https://evil.example/watch?v=123", tmp_path)
