from pathlib import Path

import ytdlp_tool.cli as cli
from ytdlp_tool.downloader import DownloadResult, SubtitleCatalog
from ytdlp_tool.media import (
    FileResult,
    FormatInfo,
    MediaInfo,
    PlaylistEntry,
    PlaylistInfo,
)


URL = "https://youtu.be/abc"


def test_info_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "inspect_media",
        lambda url: MediaInfo("abc", "Demo", "Channel", 12, URL, "desc", "thumb"),
    )
    code = cli.main(["info", URL])
    output = capsys.readouterr().out
    assert code == 0
    assert '"video_id": "abc"' in output
    assert '"title": "Demo"' in output


def test_formats_command_prints_normalized_rows(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "list_formats",
        lambda url: (FormatInfo("18", "mp4", "640x360", "avc1", "mp4a", 1234),),
    )
    code = cli.main(["formats", URL])
    output = capsys.readouterr().out
    assert code == 0
    assert "18" in output
    assert "640x360" in output
    assert "avc1" in output


def test_video_command_dispatches_options(monkeypatch, tmp_path, capsys):
    calls = []
    def fake(url, output_dir, format_selector):
        calls.append((url, output_dir, format_selector))
        return FileResult(tmp_path / "demo.mp4", "Demo", "abc", "video")
    monkeypatch.setattr(cli, "download_video", fake)
    code = cli.main(["video", URL, "--format-selector", "best",
                     "--output-dir", str(tmp_path)])
    assert code == 0
    assert calls == [(URL, Path(tmp_path), "best")]
    assert "Saved:" in capsys.readouterr().out


def test_comments_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_comments", lambda url, limit: ({"text": "hello 😓"},))
    code = cli.main(["comments", URL, "--limit", "5"])
    output = capsys.readouterr().out
    assert code == 0
    assert '"text": "hello \\ud83d\\ude13"' in output


def test_playlist_command_lists_entries(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "inspect_playlist",
        lambda url, limit: PlaylistInfo(
            "pl1", "Demo Playlist", "Channel",
            (PlaylistEntry("v1", "First", "https://youtu.be/v1"),),
        ),
    )
    code = cli.main(["playlist", "https://example.test/playlist", "--limit", "3"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Demo Playlist [pl1]" in output
    assert "First" in output


def test_subs_subcommand_reuses_subtitle_workflow(monkeypatch, tmp_path, capsys):
    calls = []
    def fake(url, language, output_format, output_dir):
        calls.append((url, language, output_format, output_dir))
        return DownloadResult(tmp_path / "demo.txt", "en", "manual", "txt", "Demo", "abc")
    monkeypatch.setattr(cli, "download_subtitle", fake)
    code = cli.main([
        "subs", URL, "--lang", "en", "--format", "txt",
        "--output-dir", str(tmp_path),
    ])
    assert code == 0
    assert calls == [(URL, "en", "txt", Path(tmp_path))]
    assert "Language: en (manual)" in capsys.readouterr().out


def test_subs_list_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "inspect_video",
        lambda url: SubtitleCatalog("abc", "Demo", ("en",), ("fa",)),
    )
    code = cli.main(["subs", URL, "--list"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Manual: en" in output
    assert "Automatic: fa" in output
