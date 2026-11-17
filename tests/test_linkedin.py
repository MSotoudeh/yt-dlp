"""LinkedIn public post extraction and Telegram delivery contract."""
from __future__ import annotations
import io
import json
import sqlite3
import subprocess
import sys

import pytest

from ytdlp_tool import cli, telegram_bot as bot

TEXT = "https://www.linkedin.com/posts/microsoft_aifirstorganisation-activity-7507725333551284224-wTby"
PHOTO = "https://it.linkedin.com/posts/microsoft_microsoftcopilot-ai-futureofwork-activity-7523661142766915584-7Ke0"
VIDEO = "https://www.linkedin.com/posts/tayloroffer_2026-will-be-the-year-of-video-on-linkedin-activity-7405991016022986752-q2Nc"
EMBED = "https://www.linkedin.com/embed/feed/update/urn:li:activity:7405991016022986752"

@pytest.mark.parametrize("url,expected", [
    (TEXT, "7507725333551284224"),
    (PHOTO, "7523661142766915584"),
    (VIDEO, "7405991016022986752"),
    (EMBED, "7405991016022986752"),
    ("https://www.linkedin.com/feed/update/urn:li:activity:7405991016022986752/?trk=feed","7405991016022986752"),
    ("https://linkedin.com/feed/update/urn:li:ugcPost:7405991016022986752","7405991016022986752"),
    ("https://de.linkedin.com/posts/member_something-share-7405991016022986752-aBCd","7405991016022986752"),
])
def test_validate_public_linkedin_post(url,expected):
    from ytdlp_tool.linkedin import validate_post_url
    assert validate_post_url(url)==expected

@pytest.mark.parametrize("url", [
    "http://www.linkedin.com/posts/user_activity-12345-X",
    "https://linkedin.com.evil.test/feed/update/urn:li:activity:1",
    "https://attacker@example.com@linkedin.com/feed/update/urn:li:activity:1",
    "https://www.linkedin.com:444/feed/update/urn:li:activity:1",
    "https://www.linkedin.com/in/test",
    "https://www.linkedin.com/jobs/view/123",
    "https://www.linkedin.com/posts/person-example-activity-1234",
    "https://www.linkedin.com/posts/person-activity-0-aBcD",
    "https://www.linkedin.com/feed/update/urn:li:activity:123/anything",
    "https://www.linkedin.com/posts/person-activity-1234567890123456789-xxxx/other",
])
def test_validate_rejects_unrelated_or_malicious_urls(url):
    from ytdlp_tool.linkedin import validate_post_url
    with pytest.raises(ValueError):
        validate_post_url(url)


def test_embed_parser_collects_only_post_text_images_video_not_avatar():
    from ytdlp_tool.linkedin import parse_embed
    raw = """<!doctype html><html><head>
    <meta property="og:description" content="Generic preview text, not author caption">
    <meta property="og:image" content="https://static.licdn.com/aero/logo">
    </head><body>
    <article data-activity-urn="urn:li:activity:7523661142766915584">
      <div role="img" data-delayed-url="https://media.licdn.com/dms/image/face.jpeg"></div>
      <p data-test-id="main-feed-activity-embed-card__commentary">Actual author text <a href="#">#test</a>\nline 2</p>
      <ul data-test-id="feed-images-content">
        <li data-test-id="feed-images-content__list-item" data-position="0">
          <img data-delayed-url="https://media.licdn.com/dms/image/one.jpg">
        </li>
        <li data-test-id="feed-images-content__list-item" data-position="1">
          <img data-delayed-url="https://media.licdn.com/dms/image/two.jpg">
          <div data-test-id="feed-images-content__overlay">+4</div>
        </li>
      </ul>
    </article></body></html>"""
    post=parse_embed(raw,"7523661142766915584")
    assert post.text=="Actual author text #test\nline 2"
    assert len(post.media)==2
    assert post.media[0].urls==("https://media.licdn.com/dms/image/one.jpg",)
    assert post.media[1].urls==("https://media.licdn.com/dms/image/two.jpg",)
    assert post.media[0].kind=="photo"
    assert any("4" in w for w in post.warnings)


def test_embed_parser_reads_mp4_variants_in_quality_order_without_preview():
    from ytdlp_tool.linkedin import parse_embed
    variants=json.dumps([
        {"src":"https://dms.licdn.com/playlist/video-low.mp4","type":"video/mp4","data-bitrate":200000},
        {"src":"https://dms.licdn.com/playlist/video-high.mp4","type":"video/mp4","data-bitrate":900000},
        {"src":"https://dms.licdn.com/playlist/stream.m3u8","type":"application/vnd.apple.mpegurl"},
    ])
    from html import escape
    raw=f'''<article data-activity-urn="urn:li:activity:7405991016022986752">
    <p data-test-id="main-feed-activity-embed-card__commentary">Video author text</p>
    <div data-test-id="feed-native-video-content"><video class="share-native-video__node" data-sources="{escape(variants,quote=True)}"></video></div>
    </article>'''
    post=parse_embed(raw,"7405991016022986752")
    assert post.text=="Video author text"
    assert len(post.media)==1
    assert post.media[0].kind=="video"
    assert post.media[0].urls==(
        "https://dms.licdn.com/playlist/video-high.mp4",
        "https://dms.licdn.com/playlist/video-low.mp4"
    )


def test_html_parser_rejects_mismatching_activity_id():
    from ytdlp_tool.linkedin import parse_embed, LinkedInError
    with pytest.raises(LinkedInError, match="mismatch|unavailable"):
        parse_embed('<article data-activity-urn="urn:li:activity:99"><p data-test-id="main-feed-activity-embed-card__commentary">Other post</p></article>',"7405991016022986752")


def test_linkedin_photo_download_rejects_external_redirect(monkeypatch,tmp_path):
    import ytdlp_tool.linkedin as li
    class R:
        status_code=302
        headers={"Location":"https://evil.test/image.jpg"}
        def __enter__(self):return self
        def __exit__(self,*a):return False
    monkeypatch.setattr(li.requests,"get",lambda *a,**kw:R())
    with pytest.raises(li.LinkedInError,match="unavailable|redirect|302"):
        li._download_media(li.LinkedInMedia("photo",("https://media.licdn.com/a.jpg",)),tmp_path/"01")
    assert not list(tmp_path.iterdir())


def test_bare_and_embedded_linkedin_urls_route_to_linkedin_job():
    assert bot.parse(PHOTO)==("li_post",PHOTO)
    assert bot.parse("/linkedin "+VIDEO)==("li_post",VIDEO)
    assert bot.parse("/li "+TEXT)==("li_post",TEXT)
    assert bot.parse("/lipost "+EMBED)==("li_post",EMBED)
    db=sqlite3.connect(":memory:")
    bot.setup(db)
    bot.ingest(db,{"update_id":450,"message":{"chat":{"id":7},"text":"Look at this "+PHOTO}})
    assert db.execute("SELECT mode,url FROM jobs WHERE update_id=450").fetchone()==("li_post",PHOTO)


def test_linkedin_cli_outputs_text_and_media(monkeypatch,tmp_path,capsys):
    from ytdlp_tool.linkedin import LinkedInDownload
    path=tmp_path/"01.jpg"
    monkeypatch.setattr(cli,"download_linkedin_post",lambda url,output:LinkedInDownload("Author text",tmp_path/"linkedin-42.txt",(path,),()),raising=False)
    assert cli.main(["li-post",PHOTO,"--output-dir",str(tmp_path)])==0
    stdout=capsys.readouterr().out
    assert "Media:" in stdout and "Text:" in stdout


def test_bot_linkedin_native_media_then_text_with_no_txt_attachment(monkeypatch,tmp_path):
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db,{"update_id":44,"message":{"chat":{"id":99,"type":"private"},"from":{"id":99},"text":PHOTO}})
    events=[]
    def fake_proc(cmd,**kw):
        assert "li-post" in cmd
        work=tmp_path/"downloads"/"44"
        work.mkdir(parents=True,exist_ok=True)
        (work/"linkedin-7523661142766915584.txt").write_text("LinkedIn authored text ✨",encoding="utf-8")
        (work/"01.jpg").write_bytes(b"\xff\xd8\xff")
        return subprocess.CompletedProcess(cmd,0,stdout="Media: 01.jpg\nText: linkedin.txt\n",stderr="")
    monkeypatch.setattr(bot.subprocess,"run",fake_proc)
    monkeypatch.setattr(bot,"send_native_media",lambda token,chat,paths:events.append(("media",len(paths))))
    monkeypatch.setattr(bot,"send_caption_text",lambda token,chat,text:events.append(("text",text)))
    monkeypatch.setattr(bot,"upload",lambda *args:pytest.fail("No TXT document should be sent"))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","99")
    monkeypatch.setattr(sys,"argv",["bot","--once","--root",str(tmp_path),"--model-dir",str(tmp_path)])
    bot.main()
    assert events==[("media",1),("text","LinkedIn authored text ✨")]
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        assert db.execute("SELECT state FROM jobs").fetchone()[0]=="done"


def test_linkedin_animated_gif_is_kept_as_animation_under_50mb(monkeypatch,tmp_path):
    import ytdlp_tool.linkedin as li

    class Response:
        status_code=200
        headers={"content-length": str(11_056_528), "content-type":"image/gif"}
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def iter_content(self,chunk_size):
            yield b"GIF89a" + b"animated"
    monkeypatch.setattr(li.requests,"get",lambda *a,**kw:Response())
    path=li._download_media(li.LinkedInMedia("photo",("https://media.licdn.com/dms/image/animated",)),tmp_path/"01")
    assert path.name=="01.gif"
    assert path.read_bytes().startswith(b"GIF89a")


def test_telegram_native_animation_uses_send_animation_not_photo(monkeypatch,tmp_path):
    import ytdlp_tool.telegram_bot as bot
    class R:
        def __enter__(self):return io.BytesIO(b'{"ok":true,"result":{}}')
        def __exit__(self,*a):return False
    seen=[]
    def fake_open(req,timeout=None):
        seen.append(req)
        return R()
    monkeypatch.setattr(bot,"urlopen",fake_open)
    gif=tmp_path/"animated.gif"
    gif.write_bytes(b"GIF89a" + b"hello")
    bot.send_native_media("token", 11, [gif])
    assert len(seen)==1
    assert seen[0].full_url.endswith("/sendAnimation")
    assert b"image/gif" in seen[0].data
    assert "animated" not in seen[0].full_url


def test_telegram_native_mixed_gif_and_images_sent_in_order(monkeypatch,tmp_path):
    import ytdlp_tool.telegram_bot as bot
    class R:
        def __enter__(self):return io.BytesIO(b'{"ok":true,"result":{}}')
        def __exit__(self,*a):return False
    calls=[]
    monkeypatch.setattr(bot,"urlopen",lambda req,timeout=None:(calls.append(req.full_url.rsplit("/",1)[-1]) or R()))
    a=tmp_path/"a.jpg"; b=tmp_path/"b.gif";c=tmp_path/"c.mp4"
    a.write_bytes(b"\xff\xd8\xff"); b.write_bytes(b"GIF89a");c.write_bytes(b"\x00\x00\x00\x14ftypisom")
    bot.send_native_media("token",11,[a,b,c])
    assert calls==["sendPhoto","sendAnimation","sendVideo"]


def test_linkedin_media_upload_failure_marks_job_failed_but_still_sends_text(monkeypatch,tmp_path):
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        bot.setup(db)
        bot.ingest(db,{"update_id":55,"message":{"chat":{"id":101,"type":"private"},
                     "from":{"id":101},"text":PHOTO}})
    events=[]
    def fake_cli(cmd,**kw):
        folder=tmp_path/"downloads"/"55"
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"linkedin-7523661142766915584.txt").write_text("Author commentary survives",encoding="utf-8")
        (folder/"01.jpg").write_bytes(b"\xff\xd8\xff")
        return subprocess.CompletedProcess(cmd,0,stdout="",stderr="")
    monkeypatch.setattr(bot.subprocess,"run",fake_cli)
    monkeypatch.setattr(bot,"send_native_media",lambda *args:(_ for _ in ()).throw(RuntimeError("Telegram sendMediaGroup 429")))
    monkeypatch.setattr(bot,"send_caption_text",lambda token,chat,text:events.append(("text",text)))
    monkeypatch.setattr(bot,"send",lambda token,chat,text,**kw:events.append(("notice",text)))
    monkeypatch.setenv("YTDL_TELEGRAM_BOT_TOKEN","test")
    monkeypatch.setenv("YTDL_ALLOWED_CHAT_IDS","101")
    monkeypatch.setattr(sys,"argv",["bot","--once","--root",str(tmp_path),"--model-dir",str(tmp_path)])
    bot.main()
    with sqlite3.connect(tmp_path/"jobs.sqlite") as db:
        state,error=db.execute("SELECT state,error FROM jobs WHERE update_id=55").fetchone()
    assert state=="failed", (state,error)
    assert error and "Telegram sendMediaGroup 429" in error
    assert any(kind=="text" and text=="Author commentary survives" for kind,text in events)
