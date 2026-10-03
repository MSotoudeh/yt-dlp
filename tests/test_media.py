from pathlib import Path

import ytdlp_tool.media as media


VIDEO_INFO = {
    "id": "abc123",
    "title": "Example Video",
    "uploader": "Example Channel",
    "duration": 125,
    "webpage_url": "https://youtu.be/abc123",
    "description": "Demo description",
    "thumbnail": "https://example.test/thumb.jpg",
    "formats": [
        {"format_id": "18", "ext": "mp4", "width": 640, "height": 360,
         "vcodec": "avc1", "acodec": "mp4a", "filesize": 1234},
        {"format_id": "140", "ext": "m4a", "vcodec": "none",
         "acodec": "mp4a", "filesize_approx": 5678},
    ],
}


class FakeYoutubeDL:
    calls = []
    created_suffix = ".mp4"

    def __init__(self, options):
        self.options = options
        type(self).calls.append(options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=False):
        if self.options.get("extract_flat"):
            return {
                "id": "pl1", "title": "Playlist", "uploader": "Channel",
                "entries": [
                    {"id": "v1", "title": "One", "url": "https://youtu.be/v1"},
                    {"id": "v2", "title": "Two", "url": "https://youtu.be/v2"},
                ],
            }
        if download:
            outtmpl = self.options["outtmpl"]
            folder = Path(outtmpl).parent
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"Example Video [abc123]{type(self).created_suffix}"
            path.write_text("data", encoding="utf-8")
            return {**VIDEO_INFO, "_filename": str(path)}
        return VIDEO_INFO


def setup_function():
    FakeYoutubeDL.calls = []
    FakeYoutubeDL.created_suffix = ".mp4"


def test_inspect_media_returns_core_metadata(monkeypatch):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    info = media.inspect_media("https://youtu.be/abc123")
    assert info.video_id == "abc123"
    assert info.title == "Example Video"
    assert info.uploader == "Example Channel"
    assert info.duration == 125


def test_list_formats_returns_normalized_formats(monkeypatch):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    formats = media.list_formats("https://youtu.be/abc123")
    assert [item.format_id for item in formats] == ["18", "140"]
    assert formats[0].resolution == "640x360"
    assert formats[1].vcodec == "none"


def test_download_video_sets_format_and_returns_created_file(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    result = media.download_video("https://youtu.be/abc123", tmp_path, "best")
    assert result.path.exists()
    assert result.kind == "video"
    assert FakeYoutubeDL.calls[-1]["format"] == "best"
    assert FakeYoutubeDL.calls[-1]["noplaylist"] is True


def test_download_audio_configures_ffmpeg_postprocessor(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    FakeYoutubeDL.created_suffix = ".mp3"
    result = media.download_audio("https://youtu.be/abc123", tmp_path, "mp3", "192")
    pp = FakeYoutubeDL.calls[-1]["postprocessors"][0]
    assert result.kind == "audio"
    assert pp["key"] == "FFmpegExtractAudio"
    assert pp["preferredcodec"] == "mp3"
    assert pp["preferredquality"] == "192"


def test_download_thumbnail_skips_media(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    FakeYoutubeDL.created_suffix = ".jpg"
    result = media.download_thumbnail("https://youtu.be/abc123", tmp_path)
    options = FakeYoutubeDL.calls[-1]
    assert result.kind == "thumbnail"
    assert options["skip_download"] is True
    assert options["writethumbnail"] is True


def test_get_comments_applies_limit(monkeypatch):
    class CommentYDL(FakeYoutubeDL):
        def extract_info(self, url, download=False):
            return {**VIDEO_INFO, "comments": [{"text": "a"}, {"text": "b"}]}
    monkeypatch.setattr(media, "YoutubeDL", CommentYDL)
    assert media.get_comments("https://youtu.be/abc123", limit=1) == ({"text": "a"},)
    assert FakeYoutubeDL.calls[-1]["extractor_args"]["youtube"]["max_comments"] == ["1"]


def test_inspect_playlist_uses_flat_playlist(monkeypatch):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    playlist = media.inspect_playlist("https://www.youtube.com/playlist?list=pl1", limit=10)
    assert playlist.playlist_id == "pl1"
    assert [entry.video_id for entry in playlist.entries] == ["v1", "v2"]
    assert FakeYoutubeDL.calls[-1]["extract_flat"] == "in_playlist"
    assert FakeYoutubeDL.calls[-1]["playlistend"] == 10


def test_download_clip_sets_download_range(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(media, "download_range_func", lambda chapters, ranges: ("ranges", ranges))
    result = media.download_clip(
        "https://youtu.be/abc123", "01:00", "01:30", tmp_path, "best"
    )
    options = FakeYoutubeDL.calls[-1]
    assert result.kind == "clip"
    assert options["download_ranges"] == ("ranges", [(60.0, 90.0)])
    assert options["force_keyframes_at_cuts"] is True


def test_parse_timestamp_accepts_seconds_and_colon_notation():
    assert media.parse_timestamp("90.5") == 90.5
    assert media.parse_timestamp("01:30") == 90.0
    assert media.parse_timestamp("1:02:03") == 3723.0


def test_download_playlist_sets_playlist_options(monkeypatch, tmp_path):
    monkeypatch.setattr(media, "YoutubeDL", FakeYoutubeDL)
    result = media.download_playlist(
        "https://example.test/playlist", tmp_path, mode="video", limit=2
    )
    options = FakeYoutubeDL.calls[-1]
    assert result.mode == "video"
    assert len(result.paths) == 1
    assert options["noplaylist"] is False
    assert options["playlistend"] == 2
    assert "%(playlist_index)03d" in options["outtmpl"]
