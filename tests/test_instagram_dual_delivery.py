
import subprocess
import sys
from pathlib import Path

import pytest
import ytdlp_tool.instagram as ig
import ytdlp_tool.telegram_bot as bot
import ytdlp_tool.cli as cli


IG_LINK = "https://www.instagram.com/reel/TEST123/"
PHOTO_LINK = "https://www.instagram.com/p/TEST123/"


def test_instagram_media_reel_prefers_yt_dlp_video(monkeypatch, tmp_path):
    from ytdlp_tool.media import FileResult
    sent = []
    file = tmp_path / "video.mp4"
    file.write_bytes(b"video")

    def fake_video(url, output_dir):
        sent.append(("video", url))
        return FileResult(file, "video", "test", "video")

    monkeypatch.setattr(ig, "download_video", fake_video, raising=False)
    monkeypatch.setattr(ig, "_download_gallery_media", lambda *a: pytest.fail("No photo extractor for reel"), raising=False)
    paths = ig.download_instagram_media(IG_LINK, tmp_path)
    assert paths == (file,)
    assert sent == [("video", IG_LINK)]


def test_instagram_media_photo_uses_gallery_without_cookies(monkeypatch, tmp_path):
    calls = []
    def fake_run(args, **kw):
        calls.append(args)
        output = tmp_path / "gallery"
        output.mkdir(exist_ok=True)
        (output / "photo1.jpg").write_bytes(b"one")
        (output / "photo2.jpg").write_bytes(b"two")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(ig.subprocess, "run", fake_run)
    result = ig.download_instagram_media(PHOTO_LINK, tmp_path)
    assert len(result) == 2
    assert [p.suffix for p in result] == [".jpg", ".jpg"]
    assert "--config-ignore" in calls[0]
    assert "--directory" in calls[0]
    assert "--cookies-from-browser" not in calls[0]
    assert "--cookies" not in calls[0]


def test_media_cli_prints_paths(monkeypatch, tmp_path, capsys):
    f=tmp_path/"reel.mp4"
    monkeypatch.setattr(cli, "download_instagram_media", lambda url, dest: (f,), raising=False)
    assert cli.main(["ig-media", IG_LINK, "--output-dir", str(tmp_path)]) == 0
    assert str(f) in capsys.readouterr().out


def test_caption_job_sends_media_then_text_and_no_txt_file(monkeypatch, tmp_path):
    import sqlite3
    root = tmp_path / "work"
    root.mkdir()
    with sqlite3.connect(root / "jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db, {"update_id": 30, "message": {
            "chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": IG_LINK,
        }})
    calls, output = [], []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        folder = root / "downloads" / "30"
        folder.mkdir(parents=True, exist_ok=True)
        if "ig-caption" in cmd:
            (folder / "instagram-TEST123-caption.txt").write_text("Written author caption", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="Source: instagram_post_caption", stderr="")
        if "ig-media" in cmd:
            media = folder / "reel.mp4"
            media.write_bytes(b"fake_video")
            return subprocess.CompletedProcess(cmd, 0, stdout="Media: " + str(media), stderr="")
        pytest.fail("unexpected CLI: " + str(cmd))

    monkeypatch.setattr(bot.subprocess, "run", fake_run)
    monkeypatch.setattr(bot, "send_instagram_media", lambda token, chat, paths: output.append(("media",tuple(paths))), raising=False)
    monkeypatch.setattr(bot, "send_caption_text", lambda token, chat, text: output.append(("text",text)))
    monkeypatch.setattr(bot, "upload", lambda *args: pytest.fail("No txt document upload"))
    monkeypatch.setattr(bot, "send", lambda *a, **kw: output.append(("status",a[2])))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","7")
    monkeypatch.setattr(sys, "argv", ["bot","--once","--root",str(root),"--model-dir",str(root)])
    bot.main()
    assert [x[0] for x in output] == ["media","text"], output
    assert output[1][1] == "Written author caption"
    assert any("ig-media" in cmd for cmd in calls)
    assert any("ig-caption" in cmd for cmd in calls)


def test_failed_media_still_sends_caption_and_explains_failure(monkeypatch, tmp_path):
    import sqlite3
    root=tmp_path/"root"
    root.mkdir()
    with sqlite3.connect(root/"jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db, {"update_id":42, "message":{"chat":{"id":9},"from":{"id":9},"text": IG_LINK}})
    sent=[]
    def fake_run(cmd, **kw):
        folder=root/"downloads"/"42"
        folder.mkdir(parents=True,exist_ok=True)
        if "ig-caption" in cmd:
            (folder/"instagram-TEST123-caption.txt").write_text("Caption survives.",encoding="utf-8")
            return subprocess.CompletedProcess(cmd,0,stdout="",stderr="")
        return subprocess.CompletedProcess(cmd,1,stdout="",stderr="login required")
    monkeypatch.setattr(bot.subprocess,"run",fake_run)
    monkeypatch.setattr(bot,"send",lambda t,c,m,**kw:sent.append(m))
    monkeypatch.setattr(bot,"upload",lambda *a:pytest.fail("File upload not requested"))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","9")
    monkeypatch.setattr(sys,"argv",["bot","--once","--root",str(root),"--model-dir",str(root)])
    bot.main()
    assert any("Caption survives." in text for text in sent)
    assert any("media" in text.lower() or "login" in text.lower() for text in sent)


def test_telegram_native_photo_video_upload_and_album(monkeypatch, tmp_path):
    import io
    import json
    import ytdlp_tool.telegram_bot as bot

    class FakeResponse:
        def __enter__(self):
            return io.BytesIO(b'{"ok": true, "result": []}')
        def __exit__(self, exc_type, exc, tb):
            return False

    requests = []
    def fake_open(req, timeout=None):
        requests.append(req)
        return FakeResponse()

    monkeypatch.setattr(bot, "urlopen", fake_open)
    photo = tmp_path / "Persian name  عکس.jpg"
    video = tmp_path / "Video ｜ clip.mp4"
    photo.write_bytes(b"fake-jpeg")
    video.write_bytes(b"fake-video")
    bot.send_instagram_media("test", 123, [photo])
    bot.send_instagram_media("test", 123, [video])
    bot.send_instagram_media("test", 123, [photo, video])

    assert len(requests) == 3
    assert requests[0].full_url.endswith("/sendPhoto")
    assert requests[1].full_url.endswith("/sendVideo")
    assert requests[2].full_url.endswith("/sendMediaGroup")
    assert b"fake-jpeg" in requests[0].data
    assert b"fake-video" in requests[1].data
    assert b"attach://media0" in requests[2].data
    assert b"attach://media1" in requests[2].data
    assert b"media0" in requests[2].data
    assert b"media1" in requests[2].data
    assert b"document" not in requests[2].data.lower()


def test_native_telegram_media_rejects_unsupported_media_without_upload(monkeypatch,tmp_path):
    import ytdlp_tool.telegram_bot as bot
    bad = tmp_path / "file.txt"
    bad.write_text("not media")
    monkeypatch.setattr(bot, "urlopen", lambda *a, **kw: pytest.fail("No upload"))
    with pytest.raises(ValueError, match="Unsupported"):
        bot.send_instagram_media("test", 123, [bad])


def test_telegram_media_album_chunks_at_ten_items(monkeypatch,tmp_path):
    import io
    import ytdlp_tool.telegram_bot as bot
    seen = []
    class Ok:
        def __enter__(self): return io.BytesIO(b'{"ok":true,"result":[]}')
        def __exit__(self, *args): return False
    def open_req(req, timeout=None):
        seen.append(req.full_url.rsplit("/",1)[1])
        return Ok()
    monkeypatch.setattr(bot, "urlopen", open_req)
    paths=[]
    for i in range(11):
        p=tmp_path/f"{i:02d}.jpg"
        p.write_bytes(b"photo")
        paths.append(p)
    bot.send_instagram_media("token", 123, paths)
    assert seen==["sendMediaGroup","sendPhoto"]


def test_instagram_post_video_fallback_preserves_multiple_items(monkeypatch, tmp_path):
    from ytdlp_tool.media import FileResult, MediaError
    monkeypatch.setattr(ig, "_download_gallery_media", lambda *a: (
        _ for _ in ()).throw(MediaError("Public gallery requires login")),
    )

    def video_download(url, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        first=output_dir/"clip1.mp4"
        second=output_dir/"clip2.mp4"
        first.write_bytes(b"1")
        second.write_bytes(b"2")
        return FileResult(first, "Post with clips", "abc", "video")

    monkeypatch.setattr(ig, "download_video", video_download)
    result=ig.download_instagram_media(PHOTO_LINK, tmp_path)
    assert [p.name for p in result] == ["clip1.mp4","clip2.mp4"]


def test_bot_marks_job_failed_when_both_instagram_caption_and_media_inaccessible(monkeypatch, tmp_path):
    import sqlite3
    import sys
    import ytdlp_tool.telegram_bot as bot

    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db, {"update_id": 99, "message": {
            "chat": {"id": 5, "type": "private"}, "from": {"id": 5},
            "text": IG_LINK,
        }})

    replies = []
    monkeypatch.setattr(bot.subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, stdout="", stderr="login required"))
    monkeypatch.setattr(bot, "send", lambda t, c, message, **kw: replies.append(message))
    monkeypatch.setattr(bot, "send_instagram_media", lambda *a: pytest.fail("No media"))
    monkeypatch.setattr(bot, "send_caption_text", lambda *a: pytest.fail("No caption"))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "5")
    monkeypatch.setattr(sys, "argv", [
        "bot", "--once", "--root", str(tmp_path), "--model-dir", str(tmp_path),
    ])

    bot.main()
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        state, error = db.execute("SELECT state,error FROM jobs WHERE update_id=99").fetchone()
    assert state == "failed"
    assert error and "unavailable" in error.lower()
    assert len(replies) >= 1
