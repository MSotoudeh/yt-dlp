
import pytest

import ytdlp_tool.instagram as ig
from ytdlp_tool.media import MediaError, MediaInfo
from ytdlp_tool.transcribe import TranscriptResult


URL = "https://www.instagram.com/reel/C-ABC_12/?igsh=tracking"


@pytest.mark.parametrize("url", [
    "https://instagram.com/reel/AX-3_9/",
    "https://www.instagram.com/p/ABC123/",
    "https://m.instagram.com/tv/ABC123",
    URL,
])
def test_instagram_url_validation_accepts_media_only(url):
    assert ig.validate_instagram_url(url)


@pytest.mark.parametrize("url", [
    "https://instagram.com/stories/user/1/",
    "https://instagram.com/username/",
    "https://instagram.com/p/",
    "https://instagram.com.evil.test/reel/123",
    "https://instagram.com@evil.test/reel/123",
    "http://instagram.com/reel/123",
    "https://www.instagram.com:1234/reel/123",
    "https://instagram.com/p/ABC/other",
])
def test_instagram_validation_rejects_unsafe_or_unsupported_paths(url):
    with pytest.raises(ValueError):
        ig.validate_instagram_url(url)


def test_post_caption_is_metadata_only_and_utf8(monkeypatch, tmp_path):
    calls = []

    def fake_info(url):
        calls.append(url)
        return MediaInfo("999", "Title", "writer", 10, url,
                         "This is the AUTHOR text ✨ #test\nline 2", None)

    monkeypatch.setattr(ig, "inspect_media", fake_info)
    monkeypatch.setattr(
        ig, "transcribe_media",
        lambda *args, **kwargs: pytest.fail("Do not run speech recognition for caption"),
    )
    result = ig.extract_post_caption(URL, tmp_path)
    assert calls == [URL]
    assert result.source == "instagram_post_caption"
    assert result.path.name == "instagram-C-ABC_12-caption.txt"
    assert result.path.read_text(encoding="utf-8") == "This is the AUTHOR text ✨ #test\nline 2\n"
    assert not list(tmp_path.rglob("*.mp3"))


@pytest.mark.parametrize("description", [None, "", "   "])
def test_missing_caption_is_not_replaced_with_title(monkeypatch, tmp_path, description):
    monkeypatch.setattr(ig, "inspect_media", lambda url: MediaInfo(
        "999", "Title must not substitute caption", None, 10, url,
        description, None,
    ))
    with pytest.raises(MediaError, match="absent or inaccessible"):
        ig.extract_post_caption(URL, tmp_path)
    assert not list(tmp_path.glob("*"))


@pytest.mark.parametrize("fmt,extension", [("txt", ".txt"), ("srt", ".srt")])
def test_ig_speech_extracts_selected_format_with_auto_language(monkeypatch, tmp_path, fmt, extension):
    calls = []

    def fake_asr(url, folder, language, model, **kwargs):
        calls.append((url, folder, language, model, kwargs["model_dir"]))
        return TranscriptResult(tmp_path / "recognized.txt", tmp_path / "recognized.srt",
                                tmp_path / "audio.m4a", None, "it", 3)

    monkeypatch.setattr(ig, "transcribe_media", fake_asr)
    result = ig.extract_spoken_text(
        URL, tmp_path, fmt, model="large-v3", model_dir=tmp_path / "models",
    )
    assert result.path.suffix == extension
    assert result.language == "it"
    assert result.source == "asr"
    assert calls == [(URL, tmp_path, "auto", "large-v3", tmp_path / "models")]


def test_ig_speech_rejects_bad_format_without_asr(monkeypatch, tmp_path):
    monkeypatch.setattr(ig, "transcribe_media", lambda *a, **kw: pytest.fail("No ASR"))
    with pytest.raises(ValueError, match="format"):
        ig.extract_spoken_text(URL, tmp_path, "xml")
