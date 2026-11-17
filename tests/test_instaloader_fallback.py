from types import SimpleNamespace
import pytest

import ytdlp_tool.instagram as ig
from ytdlp_tool.media import MediaError


PHOTO_URL = "https://www.instagram.com/p/DelZ5g8l8Pr/"
CAROUSEL_URL = "https://www.instagram.com/p/Dek_RAKjMDJ/"


def test_photo_caption_from_instaloader_does_not_touch_video_or_asr(monkeypatch, tmp_path):
    image_post = SimpleNamespace(typename="GraphImage", caption="Photo caption ✨\n#public")
    monkeypatch.setattr(ig, "_load_instaloader_post",
                        lambda shortcode: (object(), image_post), raising=False)
    monkeypatch.setattr(ig, "inspect_media", lambda *args: pytest.fail("No yt-dlp for image caption"))
    monkeypatch.setattr(ig, "transcribe_media", lambda *args, **kwargs: pytest.fail("No ASR"))
    result = ig.extract_post_caption(PHOTO_URL, tmp_path)
    assert result.path.read_text("utf-8") == "Photo caption ✨\n#public\n"
    assert result.source == "instagram_post_caption"


def test_carousel_extracts_all_images_in_order_without_gallery_dl(monkeypatch, tmp_path):
    class FakeContext:
        def get_raw(self, url):
            return SimpleNamespace(status_code=200, content=b"\xff\xd8\xff" + url.encode(),
                                   url=url, headers={"content-type": "image/jpeg"})

    nodes = [
        SimpleNamespace(is_video=False, display_url=f"https://scontent-fco2-1.cdninstagram.com/slide{i}.jpg")
        for i in range(8)
    ]
    post=SimpleNamespace(typename="GraphSidecar", get_sidecar_nodes=lambda: iter(nodes))
    monkeypatch.setattr(ig,"_load_instaloader_post",lambda code:(FakeContext(),post),raising=False)
    monkeypatch.setattr(ig,"_download_gallery_media",lambda *a:pytest.fail("Gallery-dl fallback unnecessary"))
    monkeypatch.setattr(ig,"download_video",lambda *a:pytest.fail("No video fallback"))
    paths=ig.download_instagram_media(CAROUSEL_URL,tmp_path)
    assert len(paths)==8
    assert [p.name for p in paths]==[f"{i:02d}.jpg" for i in range(1,9)]
    assert all(p.read_bytes().startswith(b"\xff\xd8\xff") for p in paths)


def test_anonymous_instaloader_rejects_untrusted_media_host(monkeypatch,tmp_path):
    class FakeContext:
        def get_raw(self,*a):
            pytest.fail("Untrusted media URL must not be fetched")
    post=SimpleNamespace(typename="GraphImage",url="https://example.net/unsafe.jpg",is_video=False)
    monkeypatch.setattr(ig,"_load_instaloader_post",lambda code:(FakeContext(),post),raising=False)
    with pytest.raises(MediaError, match="CDN"):
        ig._download_instaloader_media(PHOTO_URL,tmp_path)


def test_carousel_empty_and_non_jpeg_payload_rejected(monkeypatch,tmp_path):
    class FakeContext:
        def get_raw(self,url):
            return SimpleNamespace(status_code=200,content=b"<html>not a photo</html>",url=url,
                                   headers={"content-type": "text/html"})
    post=SimpleNamespace(typename="GraphImage",
                         url="https://scontent-fco2-1.cdninstagram.com/test.jpg",
                         is_video=False)
    monkeypatch.setattr(ig,"_load_instaloader_post",lambda code:(FakeContext(),post),raising=False)
    with pytest.raises(MediaError,match="image|media|JPEG"):
        ig._download_instaloader_media(PHOTO_URL,tmp_path)
    assert not list(tmp_path.rglob("*.jpg"))


def test_all_photo_extractors_fail_as_media_error_not_name_error(monkeypatch, tmp_path):
    monkeypatch.setattr(ig, "_download_instaloader_media", lambda *a: (
        _ for _ in ()).throw(MediaError("instaloader anonymous access denied"))
    )
    monkeypatch.setattr(ig, "_download_gallery_media", lambda *a: (
        _ for _ in ()).throw(MediaError("gallery access denied"))
    )
    monkeypatch.setattr(ig, "download_video", lambda *a: (
        _ for _ in ()).throw(MediaError("photo contains no video"))
    )
    with pytest.raises(MediaError, match="instaloader anonymous access denied"):
        ig.download_instagram_media(PHOTO_URL, tmp_path)
