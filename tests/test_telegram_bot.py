from ytdlp_tool.telegram_bot import parse, ingest, setup, format_keyboard
import sqlite3


def test_parse():
    assert parse("/audio https://youtu.be/a") == ("audio", "https://youtu.be/a")
    assert parse("/transcribe https://youtube.com/watch?v=123")[0] == "transcribe"
    assert parse("/transcript https://youtu.be/a") == ("transcript", "https://youtu.be/a")
    assert parse("https://youtu.be/a") == ("choose", "https://youtu.be/a")
    assert parse("https://www.youtube.com/watch?v=123") == ("choose", "https://www.youtube.com/watch?v=123")
    assert parse("/txt https://youtu.be/a") == ("txt", "https://youtu.be/a")
    assert parse("/srt https://youtu.be/a") == ("srt", "https://youtu.be/a")
    assert parse("https://vimeo.com/1") == ("audio", "https://vimeo.com/1")
    assert parse("/srt https://vimeo.com/1") is None
    assert parse("/video https://evil.test/a") is None
    assert parse("https://evil.test/a") is None
    assert parse("/video https://youtube.com@evil.test/") is None
    assert parse("/video http://youtube.com/a") is None
    assert parse("https://[invalid") is None


def test_dedupe():
    db = sqlite3.connect(":memory:")
    setup(db)
    msg = {"update_id": 17, "message": {"chat": {"id": 1}, "text": "/audio https://youtu.be/a"}}
    ingest(db, msg)
    ingest(db, msg)
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_bare_link_in_longer_message_offers_format_selection():
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 22, "message": {
        "chat": {"id": 3, "type": "private"},
        "from": {"id": 3},
        "text": "Please extract https://youtu.be/abc123",
    }})
    assert db.execute("SELECT mode,url FROM jobs WHERE update_id=22").fetchone() == (
        "choose", "https://youtu.be/abc123",
    )
    assert db.execute("SELECT chat,requester,url,selected FROM format_choices").fetchone() == (
        3, 3, "https://youtu.be/abc123", None,
    )
    keyboard = format_keyboard(22)
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "fmt:txt:22"
    assert keyboard["inline_keyboard"][0][1]["callback_data"] == "fmt:srt:22"


def _cb(uid, user_id, chat_id, data):
    return {"update_id": uid, "callback_query": {
        "id": "cb" + str(uid),
        "from": {"id": user_id},
        "message": {"chat": {"id": chat_id}},
        "data": data,
    }}


def test_callback_queues_srt_only_once_for_link_owner():
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 100, "message": {
        "chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "https://youtu.be/a",
    }})
    reply = ingest(db, _cb(101, 7, 7, "fmt:srt:100"))
    assert reply == "Format SRT selected."
    assert db.execute("SELECT mode,url,state FROM jobs WHERE update_id=101").fetchone() == (
        "srt", "https://youtu.be/a", "pending",
    )
    assert db.execute("SELECT selected FROM format_choices WHERE request_id=100").fetchone() == ("srt",)
    assert "already" in ingest(db, _cb(102, 7, 7, "fmt:txt:100"))
    assert db.execute("SELECT mode,state FROM jobs WHERE update_id=102").fetchone() == ("ignored", "done")
    assert db.execute("SELECT COUNT(*) FROM jobs WHERE mode IN ('txt','srt')").fetchone()[0] == 1


def test_callback_rejects_other_user_and_other_chat():
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 120, "message": {
        "chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "https://youtu.be/a",
    }})
    assert "Invalid" in ingest(db, _cb(121, 8, 7, "fmt:txt:120"))
    assert "Invalid" in ingest(db, _cb(122, 7, 8, "fmt:srt:120"))
    assert db.execute("SELECT selected FROM format_choices WHERE request_id=120").fetchone() == (None,)
    assert db.execute("SELECT COUNT(*) FROM jobs WHERE mode IN ('txt','srt')").fetchone()[0] == 0


def test_invalid_callback_is_persistently_acknowledged():
    db = sqlite3.connect(":memory:")
    setup(db)
    assert "Invalid" in ingest(db, _cb(201, 1, 1, "unexpected"))
    assert db.execute("SELECT mode,state FROM jobs WHERE update_id=201").fetchone() == ("ignored", "done")

def test_bot_delivers_only_chosen_format_without_browsing_for_other(monkeypatch, tmp_path):
    import subprocess
    import sys
    import ytdlp_tool.telegram_bot as bot

    for fmt in ("txt", "srt"):
        root = tmp_path / fmt
        root.mkdir()
        with sqlite3.connect(root / "jobs.sqlite") as db:
            setup(db)
            db.execute(
                "INSERT INTO jobs(update_id,chat,mode,url) VALUES (?,?,?,?)",
                (111, 9, fmt, "https://youtu.be/a"),
            )
            db.commit()

        calls, delivered = [], []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            folder = root / "downloads" / "111" / "captions"
            folder.mkdir(parents=True)
            (folder / ("native." + fmt)).write_text("valid text", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="Source: youtube_manual\n", stderr="")

        monkeypatch.setattr(bot.subprocess, "run", fake_run)
        monkeypatch.setattr(bot, "send", lambda *a, **kw: None)
        monkeypatch.setattr(bot, "upload", lambda token, chat, path: delivered.append(path.suffix))
        monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test-only")
        monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "9")
        monkeypatch.setattr(
            sys, "argv", [
                "telegram_bot", "--once", "--root", str(root),
                "--python", sys.executable, "--model-dir", str(root),
            ],
        )
        bot.main()
        assert len(calls) == 1
        assert calls[0][calls[0].index("--format") + 1] == fmt
        assert calls[0][calls[0].index("-m") + 1] == "ytdlp_tool"
        assert calls[0][calls[0].index("ytdlp_tool") + 1] == "transcript"
        assert delivered == ["." + fmt]
        with sqlite3.connect(root / "jobs.sqlite") as db:
            assert db.execute("SELECT state FROM jobs WHERE update_id=111").fetchone() == ("done",)


def test_bot_inline_keyboard_offered_before_any_download(monkeypatch, tmp_path):
    import sys
    import ytdlp_tool.telegram_bot as bot

    db_path = tmp_path / "jobs.sqlite"
    with sqlite3.connect(db_path) as db:
        setup(db)
        ingest(db, {"update_id": 123, "message": {
            "chat": {"id": 11, "type": "private"},
            "from": {"id": 11},
            "text": "https://youtu.be/abc123",
        }})

    sent = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kwargs: sent.append(kwargs))
    monkeypatch.setattr(
        bot.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("No download before format selection")
        ),
    )
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test-only")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "11")
    monkeypatch.setattr(sys, "argv", [
        "telegram_bot", "--once", "--root", str(tmp_path),
        "--model-dir", str(tmp_path),
    ])
    bot.main()
    assert sent[0]["keyboard"]["inline_keyboard"][0][0]["callback_data"] == "fmt:txt:123"
    assert sent[0]["keyboard"]["inline_keyboard"][0][1]["callback_data"] == "fmt:srt:123"
