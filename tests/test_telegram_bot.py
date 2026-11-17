import sqlite3

import pytest
from ytdlp_tool.telegram_bot import parse, ingest, setup, format_keyboard


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


IG_URL = "https://www.instagram.com/reel/ABC_def1/"


def test_instagram_bare_link_routes_to_three_choice_keyboard():
    assert parse(IG_URL) == ("ig_caption", IG_URL)
    assert parse("/ig_choose " + IG_URL) == ("ig_choose", IG_URL)
    assert parse("https://instagram.com/stories/creator/123456789/") == ("ig_story", "https://instagram.com/stories/creator/123456789/")
    assert parse("/igcaption " + IG_URL) == ("ig_caption", IG_URL)
    assert parse("/caption " + IG_URL) == ("ig_caption", IG_URL)
    assert parse("/igtxt " + IG_URL) == ("ig_txt", IG_URL)
    assert parse("/igsrt " + IG_URL) == ("ig_srt", IG_URL)
    assert parse("/igcaption https://www.instagram.com/stories/creator/123") == ("ig_story", "https://www.instagram.com/stories/creator/123")
    assert parse("/igcaption https://youtube.com/watch?v=test") is None
    assert parse("/srt " + IG_URL) is None

    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 302, "message": {
        "chat": {"id": 71, "type": "private"}, "from": {"id": 71},
        "text": "/ig_choose " + IG_URL,
    }})
    assert db.execute("SELECT mode,url FROM jobs").fetchone() == ("ig_choose", IG_URL)
    keyboard = format_keyboard(302, "instagram")
    buttons = [b for row in keyboard["inline_keyboard"] for b in row]
    assert [b["callback_data"] for b in buttons] == [
        "fmt:ig_caption:302", "fmt:ig_txt:302", "fmt:ig_srt:302",
    ]


def test_instagram_callback_enforces_owner_and_platform():
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 401, "message": {
        "chat": {"id": 71, "type": "private"}, "from": {"id": 71},
        "text": "/ig_choose " + IG_URL,
    }})
    assert "Invalid" in ingest(db, _cb(402, 80, 71, "fmt:ig_txt:401"))
    assert "Invalid" in ingest(db, _cb(403, 71, 71, "fmt:srt:401"))
    assert ingest(db, _cb(404, 71, 71, "fmt:ig_srt:401")) == "Format IG_SRT selected."
    assert db.execute("SELECT mode,url FROM jobs WHERE update_id=404").fetchone() == (
        "ig_srt", IG_URL,
    )
    assert "already" in ingest(db, _cb(405, 71, 71, "fmt:ig_caption:401"))


def test_instagram_keyboard_is_sent_without_download(monkeypatch, tmp_path):
    import sys
    import ytdlp_tool.telegram_bot as bot

    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        setup(db)
        ingest(db, {"update_id": 501, "message": {
            "chat": {"id": 22, "type": "private"}, "from": {"id": 22},
            "text": "/ig_choose " + IG_URL,
        }})
    sent = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: sent.append(kw))
    monkeypatch.setattr(bot.subprocess, "run", lambda *a, **kw: (
        _ for _ in ()).throw(AssertionError("Premature downloader invocation")))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test-only")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "22")
    monkeypatch.setattr(sys, "argv", [
        "bot", "--once", "--root", str(tmp_path), "--model-dir", str(tmp_path),
    ])
    bot.main()
    assert sent[0]["keyboard"]["inline_keyboard"][0][0]["callback_data"] == "fmt:ig_caption:501"


def test_instagram_job_runs_only_selected_cli_workflow(monkeypatch, tmp_path):
    import subprocess
    import sys
    import ytdlp_tool.telegram_bot as bot

    for mode, command, fmt in [
        ("ig_txt", "ig-speech", "txt"),
        ("ig_srt", "ig-speech", "srt"),
    ]:
        root = tmp_path / mode
        root.mkdir()
        with sqlite3.connect(root / "jobs.sqlite") as db:
            setup(db)
            db.execute("INSERT INTO jobs(update_id,chat,mode,url) VALUES (?,?,?,?)",
                       (123, 44, mode, IG_URL))
            db.commit()
        cmds, sent_files = [], []
        def fake_run(cmd, **kwargs):
            cmds.append(cmd)
            output = root / "downloads" / "123"
            output.mkdir(parents=True, exist_ok=True)
            ext = fmt or "txt"
            (output / ("result." + ext)).write_text("caption", encoding="utf-8")
            (output / "audio.mp3").write_text("not sent", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="Source: asr\n", stderr="")

        monkeypatch.setattr(bot.subprocess, "run", fake_run)
        monkeypatch.setattr(bot, "send", lambda *a, **kw: None)
        monkeypatch.setattr(bot, "upload", lambda token, chat, path: sent_files.append(path.suffix))
        monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test-only")
        monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "44")
        monkeypatch.setattr(sys, "argv", [
            "bot", "--once", "--root", str(root), "--model-dir", str(root),
        ])
        bot.main()
        assert cmds[0][cmds[0].index("ytdlp_tool") + 1] == command
        if fmt is not None:
            assert cmds[0][cmds[0].index("--format") + 1] == fmt
            assert "large-v3" in cmds[0]
        else:
            assert "--model" not in cmds[0]
        assert sent_files == ["." + (fmt or "txt")]
        with sqlite3.connect(root / "jobs.sqlite") as db:
            assert db.execute("SELECT state FROM jobs").fetchone() == ("done",)


def test_instagram_bare_link_queues_caption_immediately_no_buttons():
    from ytdlp_tool.telegram_bot import parse, ingest
    db = sqlite3.connect(":memory:")
    setup(db)
    url = "https://www.instagram.com/p/ABC_def1/"
    assert parse(url) == ("ig_caption", url)
    assert parse("https://www.instagram.com/reels/ABC_def1/?igsh=abc")[0] == "ig_caption"
    ingest(db, {"update_id": 610, "message": {
        "chat": {"id": 12, "type": "private"},
        "from": {"id": 12}, "text": "See this " + url,
    }})
    assert db.execute("SELECT mode,url FROM jobs").fetchone() == ("ig_caption", url)
    assert db.execute("SELECT COUNT(*) FROM format_choices").fetchone()[0] == 0


def test_story_link_is_recognized_and_does_not_download_media():
    from ytdlp_tool.telegram_bot import parse, ingest
    link = "https://www.instagram.com/stories/some.creator/3812345678901234567/?igsh=abc"
    assert parse(link) == ("ig_story", link)
    assert parse("/igcaption " + link) == ("ig_story", link)
    assert parse("https://www.instagram.com/stories/some.creator/") is None
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 801, "message": {
        "chat": {"id": 44, "type": "private"}, "text": link,
    }})
    assert db.execute("SELECT mode FROM jobs").fetchone()[0] == "ig_story"


def test_send_long_caption_in_multiple_messages_without_truncating(monkeypatch):
    import ytdlp_tool.telegram_bot as bot
    parts = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: parts.append(text))
    caption = ("Test caption ✨\n" * 700)
    bot.send_caption_text("test", 123, caption)
    assert len(parts) > 1
    assert all(len(part.encode("utf-16-le")) // 2 <= 4096 for part in parts)
    assert "".join(parts) == caption


def test_bare_ig_caption_sends_author_text_in_telegram_without_asr(monkeypatch, tmp_path):
    import sys
    import subprocess
    import ytdlp_tool.telegram_bot as bot

    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        setup(db)
        ingest(db, {"update_id": 999, "message": {
            "chat": {"id": 100, "type": "private"},
            "from": {"id": 100}, "text": IG_URL,
        }})
    commands, messages, files = [], [], []
    authored = "Author text 🔥\n#instagram"

    def fake_subprocess(cmd, **kwargs):
        commands.append(cmd)
        assert "ig-speech" not in cmd
        assert "--model" not in cmd
        destination = tmp_path / "downloads" / "999"
        destination.mkdir(parents=True, exist_ok=True)
        if "ig-caption" in cmd:
            (destination / "instagram-ABC_def1-caption.txt").write_text(authored + "\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="Source: instagram_post_caption\n", stderr="")
        assert "ig-media" in cmd
        (destination / "reel.mp4").write_bytes(b"video")
        return subprocess.CompletedProcess(cmd, 0, stdout="Media: reel.mp4\n", stderr="")

    monkeypatch.setattr(bot.subprocess, "run", fake_subprocess)
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: messages.append(text))
    monkeypatch.setattr(bot, "upload", lambda *a: pytest.fail("TXT must not be uploaded"))
    monkeypatch.setattr(bot, "send_instagram_media", lambda token, chat, paths: files.extend(p.name for p in paths))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test-only")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "100")
    monkeypatch.setattr(sys, "argv", [
        "bot", "--once", "--root", str(tmp_path), "--model-dir", str(tmp_path),
    ])
    bot.main()
    assert len(commands) == 2
    assert any(authored in m for m in messages)
    assert files == ["reel.mp4"]
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        assert db.execute("SELECT state FROM jobs WHERE update_id=999").fetchone() == ("done",)


def test_story_job_reports_metadata_limit_without_media_or_asr(monkeypatch, tmp_path):
    import sys
    import ytdlp_tool.telegram_bot as bot

    story = "https://www.instagram.com/stories/some.creator/3812345678901234567/"
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        setup(db)
        ingest(db, {"update_id": 5671, "message": {
            "chat": {"id": 10, "type": "private"}, "text": story,
        }})
    messages = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: messages.append(text))
    monkeypatch.setattr(bot.subprocess, "run", lambda *a, **kw: (
        _ for _ in ()).throw(AssertionError("Story must not download or run ASR")))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "10")
    monkeypatch.setattr(sys, "argv", [
        "bot", "--once", "--root", str(tmp_path), "--model-dir", str(tmp_path),
    ])
    bot.main()
    assert len(messages) == 1
    assert "OCR" in messages[0]
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        assert db.execute("SELECT state FROM jobs").fetchone()[0] == "done"


def test_caption_text_split_handles_only_emoji_and_no_character_loss(monkeypatch):
    import ytdlp_tool.telegram_bot as bot
    sent = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: sent.append(text))
    content = "🔥" * 4101
    bot.send_caption_text("test", 123, content)
    assert "".join(sent) == content
    assert max(len(s.encode("utf-16-le")) // 2 for s in sent) <= 4096


def test_polling_survives_transient_network_errors(monkeypatch, tmp_path):
    """A getUpdates network failure must back off and retry, not kill the bot."""
    import pytest
    from ytdlp_tool import telegram_bot

    calls = {"api": 0}
    sleeps = []

    def fake_api(token, method, params):
        calls["api"] += 1
        if calls["api"] == 1:
            raise OSError("network down")
        raise KeyboardInterrupt  # stop the otherwise endless loop

    monkeypatch.setattr(telegram_bot, "api", fake_api)
    monkeypatch.setattr(telegram_bot.time, "sleep", sleeps.append)
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "1")
    monkeypatch.setattr(
        "sys.argv",
        ["telegram_bot", "--model-dir", str(tmp_path), "--root", str(tmp_path / "state")],
    )
    with pytest.raises(KeyboardInterrupt):
        telegram_bot.main()
    assert calls["api"] == 2
    assert sleeps == [2]


def test_failure_notice_is_generic_unless_cause_is_known():
    from ytdlp_tool.telegram_bot import failure_notice

    assert failure_notice("audio", RuntimeError("anything /secret/path")) == "Job failed. Contact operator."
    assert "rate-limited" in failure_notice("transcript", RuntimeError("HTTP Error 429"))
    assert "timed out" in failure_notice("transcript", RuntimeError("Timeout expired"))
    assert "denied" in failure_notice("ig_txt", RuntimeError("login required"))
    assert "no accessible written caption" in failure_notice("ig_caption", RuntimeError("caption is absent"))
    assert "No recognizable" in failure_notice("ig_srt", RuntimeError("No speech detected"))
    # a Telegram-visible notice never echoes the raw exception text
    assert "secret" not in failure_notice("ig_caption", RuntimeError("secret 403"))


def test_wildcard_allowlist_requires_explicit_opt_in(monkeypatch):
    import pytest
    from ytdlp_tool.telegram_bot import load_allowlist

    monkeypatch.delenv("YTDL_ALLOW_PUBLIC_BOT", raising=False)
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "*")
    with pytest.raises(SystemExit):
        load_allowlist()
    monkeypatch.setenv("YTDL_ALLOW_PUBLIC_BOT", "1")
    assert load_allowlist() == {"*"}
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", " 1, 2 ,")
    assert load_allowlist() == {"1", "2"}
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS", "")
    with pytest.raises(SystemExit):
        load_allowlist()


def test_static_replies_do_not_start_subprocesses(monkeypatch):
    from ytdlp_tool import telegram_bot as bot

    sent = []
    monkeypatch.setattr(bot, "send", lambda token, chat, text, **kw: sent.append(text))
    monkeypatch.setattr(bot.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no subprocess")))
    ctx = bot.JobContext(token="t", db=None, root=None, python="py", model_dir="m")
    for mode in ("help", "invalid", "ig_story"):
        assert bot.dispatch_job(ctx, 1, 1, mode, "") is None
    assert len(sent) == 3


def test_run_logs_why_the_bot_stopped(monkeypatch, tmp_path):
    from ytdlp_tool import telegram_bot as bot

    log = tmp_path / "bot.log"
    monkeypatch.setattr(bot, "_LOG_FILE", str(log))

    def boom():
        raise ValueError("disk exploded")

    monkeypatch.setattr(bot, "main", boom)
    with pytest.raises(SystemExit) as stopped:
        bot.run()
    assert stopped.value.code == 1
    text = log.read_text(encoding="utf-8")
    assert "bot crashed" in text and "disk exploded" in text

    monkeypatch.setattr(bot, "main", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(SystemExit) as stopped:
        bot.run()
    assert stopped.value.code == 130
    assert "interrupted" in log.read_text(encoding="utf-8")


def test_log_file_failure_never_stops_the_bot(monkeypatch, tmp_path):
    from ytdlp_tool import telegram_bot as bot

    monkeypatch.setattr(bot, "_LOG_FILE", str(tmp_path / "missing-dir" / "bot.log"))
    bot._log("still fine")  # must not raise
