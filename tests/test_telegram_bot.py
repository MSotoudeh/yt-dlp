from ytdlp_tool.telegram_bot import parse, ingest, setup
import sqlite3


def test_parse():
    assert parse("/audio https://youtu.be/a") == ("audio", "https://youtu.be/a")
    assert parse("/transcribe https://youtube.com/watch?v=123")[0] == "transcribe"
    assert parse("/transcript https://youtu.be/a") == ("transcript", "https://youtu.be/a")
    assert parse("https://youtu.be/a") == ("transcript", "https://youtu.be/a")
    assert parse("https://www.youtube.com/watch?v=123") == ("transcript", "https://www.youtube.com/watch?v=123")
    assert parse("https://vimeo.com/1") == ("audio", "https://vimeo.com/1")
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


def test_bare_link_in_longer_message_uses_transcript():
    db = sqlite3.connect(":memory:")
    setup(db)
    ingest(db, {"update_id": 22, "message": {"chat": {"id": 1}, "text": "Please extract https://youtu.be/abc123"}})
    assert db.execute("SELECT mode,url FROM jobs WHERE update_id=22").fetchone() == (
        "transcript", "https://youtu.be/abc123",
    )
