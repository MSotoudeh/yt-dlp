from ytdlp_tool.telegram_bot import parse, ingest, setup
import sqlite3
def test_parse():
    assert parse("/audio https://youtu.be/a") == ("audio","https://youtu.be/a")
    assert parse("/transcribe https://youtube.com/watch?v=123")[0] == "transcribe"
    assert parse("/video https://evil.test/a") is None
    assert parse("/video https://youtube.com@evil.test/") is None
    assert parse("/video http://youtube.com/a") is None
def test_dedupe():
    db=sqlite3.connect(":memory:")
    setup(db)
    msg={"update_id":17,"message":{"chat":{"id":1},"text":"/audio https://youtu.be/a"}}
    ingest(db,msg);ingest(db,msg)
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
