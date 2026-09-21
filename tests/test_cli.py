from pathlib import Path

import ytdlp_tool.cli as cli
from ytdlp_tool.downloader import DownloadResult, SubtitleCatalog, SubtitleDownloadError
from ytdlp_tool.subtitles import SubtitleUnavailableError


def test_list_prints_manual_and_automatic_languages(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "inspect_video",
        lambda url: SubtitleCatalog("abc", "Demo", ("en", "it"), ("en", "fa")),
    )

    code = cli.main(["https://youtu.be/abc", "--list"])

    output = capsys.readouterr().out
    assert code == 0
    assert "Demo [abc]" in output
    assert "Manual: en, it" in output
    assert "Automatic: en, fa" in output


def test_download_prints_result_and_passes_arguments(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_download(url, language, output_format, output_dir):
        calls.append((url, language, output_format, output_dir))
        return DownloadResult(tmp_path / "demo.en.srt", "en", "manual", "srt", "Demo", "abc")

    monkeypatch.setattr(cli, "download_subtitle", fake_download)

    code = cli.main([
        "https://youtu.be/abc",
        "--lang", "en",
        "--format", "srt",
        "--output-dir", str(tmp_path),
    ])

    output = capsys.readouterr().out
    assert code == 0
    assert calls == [("https://youtu.be/abc", "en", "srt", Path(tmp_path))]
    assert "Saved:" in output
    assert "manual" in output


def test_download_error_returns_one_and_writes_stderr(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise SubtitleDownloadError("network failed")

    monkeypatch.setattr(cli, "download_subtitle", fail)
    code = cli.main(["https://youtu.be/abc"])
    captured = capsys.readouterr()
    assert code == 1
    assert "Error: network failed" in captured.err


def test_unavailable_language_returns_one(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise SubtitleUnavailableError("Subtitle language 'fa' is unavailable")

    monkeypatch.setattr(cli, "download_subtitle", fail)
    code = cli.main(["https://youtu.be/abc", "--lang", "fa"])
    assert code == 1
    assert "unavailable" in capsys.readouterr().err
