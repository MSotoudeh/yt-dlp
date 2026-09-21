from pathlib import Path

import pytest

import ytdlp_tool.downloader as downloader


VIDEO_INFO = {
    "id": "abc123",
    "title": "Example Video",
    "subtitles": {"en": [{"ext": "vtt", "url": "manual"}]},
    "automatic_captions": {"en": [{"ext": "vtt", "url": "auto"}], "it": [{}]},
}


class FakeYoutubeDL:
    calls = []
    output_path: Path | None = None

    def __init__(self, options):
        self.options = options
        type(self).calls.append(options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=False):
        if not download:
            return VIDEO_INFO
        path = type(self).output_path
        assert path is not None
        path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n", encoding="utf-8")
        return {**VIDEO_INFO, "requested_subtitles": {"en": {"ext": "vtt", "filepath": str(path)}}}


def setup_function():
    FakeYoutubeDL.calls = []
    FakeYoutubeDL.output_path = None


def test_inspect_video_returns_sorted_catalog(monkeypatch):
    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    catalog = downloader.inspect_video("https://youtu.be/abc123")
    assert catalog.video_id == "abc123"
    assert catalog.title == "Example Video"
    assert catalog.manual == ("en",)
    assert catalog.automatic == ("en", "it")
    assert FakeYoutubeDL.calls[0]["skip_download"] is True


def test_download_vtt_prefers_manual_and_uses_subtitle_only_options(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    FakeYoutubeDL.output_path = tmp_path / "Example Video [abc123].en.vtt"

    result = downloader.download_subtitle(
        "https://youtu.be/abc123", "en", "vtt", tmp_path
    )

    assert result.path == FakeYoutubeDL.output_path
    assert result.source == "manual"
    options = FakeYoutubeDL.calls[-1]
    assert options["skip_download"] is True
    assert options["writesubtitles"] is True
    assert options["writeautomaticsub"] is False
    assert options["subtitleslangs"] == ["en"]
    assert options["subtitlesformat"] == "vtt"


def test_download_txt_converts_vtt_and_removes_intermediate(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    source = tmp_path / "Example Video [abc123].en.vtt"
    FakeYoutubeDL.output_path = source

    result = downloader.download_subtitle(
        "https://youtu.be/abc123", "en", "txt", tmp_path
    )

    assert result.path.suffix == ".txt"
    assert result.path.read_text(encoding="utf-8") == "Hello\n"
    assert not source.exists()


def test_download_srt_converts_vtt_and_removes_intermediate(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "YoutubeDL", FakeYoutubeDL)
    source = tmp_path / "Example Video [abc123].en.vtt"
    FakeYoutubeDL.output_path = source

    result = downloader.download_subtitle(
        "https://youtu.be/abc123", "en", "srt", tmp_path
    )

    assert result.path.suffix == ".srt"
    assert "00:00:00,000 --> 00:00:01,000" in result.path.read_text(encoding="utf-8")
    assert not source.exists()


def test_rejects_unknown_output_format(tmp_path):
    with pytest.raises(ValueError):
        downloader.download_subtitle("https://youtu.be/abc123", "en", "ass", tmp_path)
