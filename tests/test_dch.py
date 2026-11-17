import base64
import io
import json
import time

import pytest
from yt_dlp.utils import DownloadError

import ytdlp_tool.cli as cli
import ytdlp_tool.dch as dch

URL = "https://www.digitalconcerthall.com/en/concert/56205"


def make_token(exp_offset=3600, **extra):
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    payload = {"sub": "fake-user", **extra}
    if exp_offset is not None:
        payload["exp"] = int(time.time()) + exp_offset
    return f"{enc({'alg': 'HS256'})}.{enc(payload)}.fake-signature"


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL; records options and can create output files."""

    instances = []
    info = {}
    error = None
    files = ()
    dest = None

    def __init__(self, options):
        self.options = options
        FakeYDL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        self.url, self.download = url, download
        if FakeYDL.error:
            raise FakeYDL.error
        if download:
            for relative in FakeYDL.files:
                path = FakeYDL.dest / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
        return FakeYDL.info


@pytest.fixture(autouse=True)
def fake_ydl(monkeypatch):
    FakeYDL.instances, FakeYDL.error, FakeYDL.files, FakeYDL.dest = [], None, (), None
    FakeYDL.info = {
        "id": "56205",
        "entries": [
            {"id": "56205-1", "title": "Symphony", "duration": 2700,
             "formats": [{"height": 720}, {"height": 1080}, {"height": None}]},
            {"id": "56205-2", "title": "Interview", "duration": 600, "formats": []},
        ],
    }
    monkeypatch.setattr(dch, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(dch.shutil, "which", lambda name: "/usr/bin/" + name)


@pytest.mark.parametrize("url", [
    URL, URL + "/", "https://digitalconcerthall.com/de/film/388",
    "https://www.digitalconcerthall.com/en/work/53785-1",
])
def test_validate_accepts_supported_pages(url):
    assert dch.validate_dch_url(url).startswith("https://")


@pytest.mark.parametrize("url", [
    "http://www.digitalconcerthall.com/en/concert/56205",
    "https://evil.test/en/concert/56205",
    "https://www.digitalconcerthall.com.evil.test/en/concert/56205",
    "https://user:pw@www.digitalconcerthall.com/en/concert/56205",
    "https://www.digitalconcerthall.com:8443/en/concert/56205",
    "https://www.digitalconcerthall.com/en/artist/12",
    "https://www.digitalconcerthall.com/en/concert/abc",
    "https://[invalid",
])
def test_validate_rejects_everything_else(url):
    with pytest.raises(ValueError):
        dch.validate_dch_url(url)


def test_validate_strips_query_and_fragment():
    assert dch.validate_dch_url(URL + "?utm=1#x") == URL


def test_token_expiry_checks():
    assert 3500 < dch.token_seconds_left(make_token(3600)) <= 3600
    assert dch.token_seconds_left(make_token(None)) is None
    with pytest.raises(dch.DchError, match="expired"):
        dch.token_seconds_left(make_token(-10))
    with pytest.raises(dch.DchError, match="expired"):
        dch.token_seconds_left(make_token(10))  # too close to expiry to finish a request
    with pytest.raises(dch.DchError, match="JWT"):
        dch.token_seconds_left("not-a-token")
    with pytest.raises(dch.DchError, match="unreadable"):
        dch.token_seconds_left("a.%%%.c")


def test_list_items_uses_in_memory_token_only():
    token = make_token()
    items = dch.list_items(URL, token)
    assert [(i.index, i.video_id, i.best_height, i.formats) for i in items] == [
        (1, "56205-1", 1080, 3), (2, "56205-2", None, 0),
    ]
    options = FakeYDL.instances[0].options
    assert options["username"] == "token" and options["password"] == token
    assert options["cachedir"] is False  # otherwise the extractor caches the token on disk
    assert options["skip_download"] is True
    assert FakeYDL.instances[0].download is False


def test_download_returns_finished_files_and_hides_token(tmp_path):
    token = make_token()
    FakeYDL.files, FakeYDL.dest = ("56205 [56205]/01 - Symphony [56205-1].mp4",), tmp_path
    result = dch.download(URL, token, tmp_path, item=1)
    assert [p.name for p in result.paths] == ["01 - Symphony [56205-1].mp4"]
    options = FakeYDL.instances[0].options
    assert options["playlist_items"] == "1"
    assert options["cachedir"] is False
    assert token not in options["outtmpl"]


def test_download_ignores_partial_files_and_reports_nothing_new(tmp_path):
    FakeYDL.files, FakeYDL.dest = ("x/01 - A.mp4.part",), tmp_path
    with pytest.raises(dch.DchError, match="no new media file"):
        dch.download(URL, make_token(), tmp_path)


def test_download_requires_ffmpeg_and_valid_item(monkeypatch, tmp_path):
    monkeypatch.setattr(dch.shutil, "which", lambda name: None)
    with pytest.raises(dch.DchError, match="ffmpeg"):
        dch.download(URL, make_token(), tmp_path)
    monkeypatch.setattr(dch.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    with pytest.raises(ValueError, match="--item"):
        dch.download(URL, make_token(), tmp_path, item=0)


def test_errors_never_contain_the_token():
    token = make_token()
    FakeYDL.error = DownloadError(f"ERROR: HTTP Error 500 while using {token}")
    with pytest.raises(dch.DchError) as caught:
        dch.list_items(URL, token)
    assert token not in str(caught.value)


def test_error_classification():
    FakeYDL.error = DownloadError("ERROR: Access token has expired or been invalidated")
    with pytest.raises(dch.DchError, match="rejected the token"):
        dch.list_items(URL, make_token())
    FakeYDL.error = DownloadError("ERROR: stream is DRM protected")
    with pytest.raises(dch.DchError, match="DRM"):
        dch.list_items(URL, make_token())


def test_cli_list_reads_token_from_stdin_and_never_prints_it(monkeypatch, capsys):
    token = make_token()
    monkeypatch.setattr("sys.stdin", io.StringIO(token + "\n"))
    assert cli.main(["dch", URL, "--list", "--token-stdin"]) == 0
    captured = capsys.readouterr()
    assert token not in captured.out + captured.err
    assert "Token valid for about" in captured.out
    assert "1080p" in captured.out and "Symphony" in captured.out


def test_cli_without_terminal_or_stdin_flag_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["dch", URL, "--list"]) == 1
    assert "--token-stdin" in capsys.readouterr().err


def test_cli_rejects_other_sites_before_reading_the_token(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(make_token() + "\n"))
    assert cli.main(["dch", "https://evil.test/en/concert/1", "--token-stdin"]) == 1
    assert "digitalconcerthall.com" in capsys.readouterr().err
