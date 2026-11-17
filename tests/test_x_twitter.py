"""Contract tests for read-only X/Twitter single-post Telegram delivery."""
import sqlite3
import subprocess
import sys

import pytest

from ytdlp_tool import cli, telegram_bot as bot


TEXT_LINK = "https://x.com/jack/status/20"
PHOTO_LINK = "https://twitter.com/30mmissions/status/1990736788097556943?s=20"
VIDEO_LINK = "https://x.com/s_hm2030/status/1993877459469783229"


@pytest.mark.parametrize("url,expected_id", [
    (TEXT_LINK, "20"),
    (PHOTO_LINK, "1990736788097556943"),
    ("https://mobile.twitter.com/a_b/status/1990736788097556943/photo/1", "1990736788097556943"),
    ("https://www.x.com/i/web/status/1993877459469783229?lang=en", "1993877459469783229"),
    ("https://www.twitter.com/someone/status/99/video/1", "99"),
])
def test_validate_x_status_link(url, expected_id):
    from ytdlp_tool.x_twitter import validate_status_url
    assert validate_status_url(url) == expected_id


@pytest.mark.parametrize("bad_url", [
    "http://x.com/jack/status/20",
    "https://x.com.evil.test/jack/status/20",
    "https://evil.com@x.com/jack/status/20",
    "https://twitter.com/jack",
    "https://x.com/jack/status/non_numeric",
    "https://x.com/jack/status/20/other/1",
    "https://x.com:9000/jack/status/20",
    "https://x.com/jack/status/0",
    "https://x.com/jack/status/20/../../abc",
    "https://x.com/jack/status/999999999999999999999999999",
])
def test_reject_unsupported_or_untrusted_status_url(bad_url):
    from ytdlp_tool.x_twitter import validate_status_url
    with pytest.raises(ValueError):
        validate_status_url(bad_url)


def test_bot_detects_bare_and_embedded_tweet_links():
    assert bot.parse(TEXT_LINK) == ("x_post", TEXT_LINK)
    assert bot.parse("/tweet " + VIDEO_LINK) == ("x_post", VIDEO_LINK)
    assert bot.parse("/x " + PHOTO_LINK) == ("x_post", PHOTO_LINK)
    assert bot.parse("/xpost " + TEXT_LINK) == ("x_post", TEXT_LINK)
    assert bot.parse("/x " + "https://x.com.evil.test/jack/status/20") is None
    db=sqlite3.connect(":memory:")
    bot.setup(db)
    bot.ingest(db,{"update_id":7,"message":{"chat":{"id":18},"text":"look " + PHOTO_LINK}})
    assert db.execute("SELECT mode,url FROM jobs").fetchone() == ("x_post",PHOTO_LINK)


def test_syndication_extract_own_author_text_and_photo_video_variants(monkeypatch):
    import ytdlp_tool.x_twitter as x
    data = {
        "__typename":"Tweet","id_str":"1993877459469783229",
        "text":"Tweet written by the author https://t.co/end",
        "quoted_tweet":{"text":"Should NOT be selected",
            "mediaDetails":[{"type":"photo","media_url_https":"https://pbs.twimg.com/quoted.jpg"}]},
        "mediaDetails":[
            {"type":"photo","media_url_https":"https://pbs.twimg.com/media/one.jpg"},
            {"type":"video","video_info":{"variants":[
                {"content_type":"application/x-mpegURL","url":"https://video.twimg.com/a/pl.m3u8"},
                {"content_type":"video/mp4","bitrate":256000,"url":"https://video.twimg.com/a/s.mp4"},
                {"content_type":"video/mp4","bitrate":832000,"url":"https://video.twimg.com/a/m.mp4"}
            ]}}
        ]
    }
    class FakeResponse:
        status_code=200
        def json(self):return data
        def raise_for_status(self):pass
    urls=[]
    def fake_get(url, **kwargs):
        urls.append(url)
        assert "cdn.syndication.twimg.com" in url
        assert kwargs["params"]["id"] == "1993877459469783229"
        return FakeResponse()
    monkeypatch.setattr(x.requests,"get",fake_get)
    post=x.fetch_post(VIDEO_LINK)
    assert post.text == "Tweet written by the author https://t.co/end"
    assert [item.kind for item in post.media]==["photo","video"]
    assert post.media[0].urls == ("https://pbs.twimg.com/media/one.jpg",)
    assert post.media[1].urls == (
        "https://video.twimg.com/a/m.mp4", "https://video.twimg.com/a/s.mp4"
    )
    assert len(urls)==1


def test_text_only_status_creates_only_text_no_media(monkeypatch,tmp_path):
    import ytdlp_tool.x_twitter as x
    monkeypatch.setattr(x,"fetch_post",lambda url:x.XPost("20","just setting up my twttr",()))
    result=x.download_post(TEXT_LINK,tmp_path)
    assert result.text == "just setting up my twttr"
    assert result.media == ()
    assert (tmp_path/"tweet-20.txt").read_text(encoding="utf-8") == result.text


def test_photo_download_rejects_malicious_host_without_network(monkeypatch,tmp_path):
    import ytdlp_tool.x_twitter as x
    monkeypatch.setattr(x,"fetch_post",lambda url:x.XPost(
        "20","Hi",(x.XMedia("photo",("https://example.org/evil.jpg",)),)
    ))
    def no_network(*args,**kwargs):
        pytest.fail("Untrusted host must not be fetched")
    monkeypatch.setattr(x.requests,"get",no_network)
    result=x.download_post(TEXT_LINK,tmp_path)
    assert result.text == "Hi"
    assert result.media == ()
    assert result.warnings and "unavailable" in result.warnings[0].lower()


def test_cli_xpost_prints_status_and_media(monkeypatch,tmp_path,capsys):
    from ytdlp_tool.x_twitter import XDownload
    photo=tmp_path/"photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(cli,"download_x_post",lambda url,folder:XDownload(
        text="a tweet",text_path=tmp_path/"tweet.txt",media=(photo,),warnings=()
    ),raising=False)
    assert cli.main(["x-post",PHOTO_LINK,"--output-dir",str(tmp_path)])==0
    output=capsys.readouterr().out
    assert "Media: " in output
    assert "Text: " in output


def test_bot_send_tweet_image_then_plain_text_no_txt(monkeypatch,tmp_path):
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db,{"update_id":17,"message":{"chat":{"id":88,"type":"private"},"from":{"id":88},"text":PHOTO_LINK}})
    events=[]
    def fake_proc(cmd,**kwargs):
        folder=tmp_path/"downloads"/"17"
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"tweet-1990736788097556943.txt").write_text("The real written tweet",encoding="utf-8")
        (folder/"01.jpg").write_bytes(b"\xff\xd8\xff")
        return subprocess.CompletedProcess(cmd,0,stdout="Media: 01.jpg\nText: tweet.txt",stderr="")
    monkeypatch.setattr(bot.subprocess,"run",fake_proc)
    monkeypatch.setattr(bot,"send_native_media",lambda token,chat,paths:events.append(("media",len(paths))),raising=False)
    monkeypatch.setattr(bot,"send_caption_text",lambda token,chat,text:events.append(("text",text)))
    monkeypatch.setattr(bot,"send",lambda token,chat,text,**kwargs:events.append(("notice",text)))
    monkeypatch.setattr(bot,"upload",lambda *args:pytest.fail("No TXT document upload"))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test-only")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","88")
    monkeypatch.setattr(sys,"argv",["bot","--once","--root",str(tmp_path),"--model-dir",str(tmp_path)])
    bot.main()
    assert events==[("media",1),("text","The real written tweet")]
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        assert db.execute("SELECT state FROM jobs").fetchone()==("done",)


def test_bot_text_only_tweet_and_media_download_failure(monkeypatch,tmp_path):
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db,{"update_id":21,"message":{"chat":{"id":9,"type":"private"},"from":{"id":9},"text":TEXT_LINK}})
    events=[]
    def fake_proc(cmd,**kwargs):
        folder=tmp_path/"downloads"/"21"
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"tweet-20.txt").write_text("Text-only tweet",encoding="utf-8")
        return subprocess.CompletedProcess(cmd,0,stdout="Text: tweet-20.txt",stderr="")
    monkeypatch.setattr(bot.subprocess,"run",fake_proc)
    monkeypatch.setattr(bot,"send_native_media",lambda *args:pytest.fail("Text tweet has no media"),raising=False)
    monkeypatch.setattr(bot,"send_caption_text",lambda token,chat,text:events.append(text))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test-only")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","9")
    monkeypatch.setattr(sys,"argv",["bot","--once","--root",str(tmp_path),"--model-dir",str(tmp_path)])
    bot.main()
    assert events==["Text-only tweet"]


def test_tweet_absent_or_protected_never_fabricates_message(monkeypatch,tmp_path):
    import ytdlp_tool.x_twitter as x
    class Response:
        status_code=200
        def raise_for_status(self):pass
        def json(self):return {"__typename":"TweetTombstone","text":"untrusted"}
    monkeypatch.setattr(x.requests,"get",lambda *a,**kw:Response())
    with pytest.raises(x.XError,match="unavailable|protected|deleted"):
        x.fetch_post(TEXT_LINK)


def test_multi_photo_tweet_preserves_order_and_does_not_use_quoted_media():
    from ytdlp_tool.x_twitter import _media_from_payload
    payload = {
        "mediaDetails": [
            {"type": "photo", "media_url_https": f"https://pbs.twimg.com/media/{n}.jpg"}
            for n in (1, 2, 3, 4)
        ],
        "quoted_tweet": {
            "mediaDetails": [{"type": "photo", "media_url_https": "https://pbs.twimg.com/quoted.jpg"}]
        }
    }
    assets = _media_from_payload(payload)
    assert len(assets) == 4
    assert [asset.urls[0].rsplit("/", 1)[-1] for asset in assets] == [
        "1.jpg", "2.jpg", "3.jpg", "4.jpg"
    ]


def test_media_download_falls_back_to_smaller_mp4(monkeypatch, tmp_path):
    from ytdlp_tool.x_twitter import XMedia, _download_one
    import ytdlp_tool.x_twitter as x

    class FakeResponse:
        def __init__(self, code, data, headers=None):
            self.status_code = code
            self._data = data
            self.headers = headers or {}
        def __enter__(self):return self
        def __exit__(self, *args):return False
        def iter_content(self, chunk_size):
            yield self._data

    seen = []
    def fake_get(url, **kw):
        seen.append(url)
        assert kw["allow_redirects"] is False
        assert kw["stream"] is True
        if url.endswith("high.mp4"):
            return FakeResponse(200, b"", {"Content-Length": str(50 * 1024 * 1024)})
        return FakeResponse(200, b"\x00\x00\x00\x14ftypisom")
    monkeypatch.setattr(x.requests, "get", fake_get)
    path = _download_one(XMedia("video", (
        "https://video.twimg.com/vid/high.mp4",
        "https://video.twimg.com/vid/low.mp4",
    )), tmp_path / "video")
    assert path.suffix == ".mp4"
    assert path.read_bytes()[4:8] == b"ftyp"
    assert len(seen) == 2


def test_media_download_rejects_http_redirect(monkeypatch, tmp_path):
    from ytdlp_tool.x_twitter import XMedia, _download_one, XError
    import ytdlp_tool.x_twitter as x
    class FakeRedirect:
        status_code=302
        headers={"Location":"https://evil.test/private"}
        def __enter__(self):return self
        def __exit__(self,*args):return False
    monkeypatch.setattr(x.requests, "get",lambda *a,**kw: FakeRedirect())
    with pytest.raises(XError,match="302"):
        _download_one(XMedia("photo",("https://pbs.twimg.com/media/1.jpg",)),tmp_path/"photo")
    assert not list(tmp_path.iterdir())


def test_syndication_protected_failure_is_explicit(monkeypatch):
    import ytdlp_tool.x_twitter as x
    class FakeResponse:
        status_code=401
        def json(self):return {"text":"Do not trust on error"}
    monkeypatch.setattr(x.requests, "get",lambda *a,**kw:FakeResponse())
    with pytest.raises(x.XError,match="401"):
        x.fetch_post(TEXT_LINK)


def test_absent_authored_text_with_media_reports_no_text_not_fabricated(monkeypatch,tmp_path):
    import ytdlp_tool.x_twitter as x
    monkeypatch.setattr(x, "fetch_post", lambda url:
        x.XPost("99", "", (x.XMedia("photo", ("https://pbs.twimg.com/pic.jpg",)),)))
    monkeypatch.setattr(x, "_download_one", lambda item, path: tmp_path/"01.jpg")
    result=x.download_post("https://x.com/user/status/99",tmp_path)
    assert result.text == ""
    assert result.media == (tmp_path/"01.jpg",)
    assert result.text_path.read_text(encoding="utf-8") == ""
