import io
import json
import os
import sys
import threading
import time

import pytest

import ytdlp_tool.dch_host as host
from test_dch import make_token

URL = "https://www.digitalconcerthall.com/en/concert/56205"


@pytest.fixture(autouse=True)
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_DCH_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("YTDLP_DCH_OUTPUT", str(tmp_path / "out"))
    return tmp_path


class FakeExtension:
    """Plays the browser extension at the far end of the native-messaging pipes."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []
        to_host_r, self.to_host_w = os.pipe()
        self.from_host_r, from_host_w = os.pipe()
        self.host = host.Host(os.fdopen(to_host_r, "rb"), os.fdopen(from_host_w, "wb"))
        self.reader = os.fdopen(self.from_host_r, "rb")
        self.writer = os.fdopen(self.to_host_w, "wb")
        threading.Thread(target=self.host.pump, daemon=True).start()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            message = host.read_message(self.reader)
            if message is None:
                return
            self.requests.append(message)
            reply = self.answer(message)
            if reply is not None:
                host.write_message(self.writer, {"id": message["id"], **reply})


def stub_worker(tmp_path):
    body = "import sys\nopen(sys.argv[1] + '/received', 'w').write(sys.stdin.readline().strip())\n"
    return [sys.executable, "-c", body, str(tmp_path)]


def test_native_message_framing_roundtrip():
    buffer = io.BytesIO()
    host.write_message(buffer, {"a": "ß✓", "n": 1})
    buffer.seek(0)
    assert host.read_message(buffer) == {"a": "ß✓", "n": 1}
    assert host.read_message(buffer) is None
    with pytest.raises(ValueError):
        host.read_message(io.BytesIO((2**31).to_bytes(4, "little") + b"x"))


def test_start_flow_token_goes_extension_to_worker_only(state):
    token = make_token()
    ext = FakeExtension(lambda m: {"token": token, "url": URL})
    ext.host.worker_command = stub_worker(state)
    response = ext.host.handle_request({"secret": ext.host.secret, "op": "start", "url": URL})
    assert response["ok"] and response["state"] == "running" and response["job_id"]
    assert token not in json.dumps(response)  # never returned to the (MCP) client
    deadline = time.time() + 10
    while not (state / "received").exists() and time.time() < deadline:
        time.sleep(0.05)
    assert (state / "received").read_text() == token
    assert ext.requests[0]["type"] == "get_token" and ext.requests[0]["url"] == URL


def test_requests_without_the_secret_are_refused(state):
    ext = FakeExtension(lambda m: {"token": make_token(), "url": URL})
    assert ext.host.handle_request({"op": "start", "url": URL}) == {"ok": False, "error": "unauthorized"}
    assert ext.host.handle_request({"secret": "wrong", "op": "start", "url": URL})["error"] == "unauthorized"
    assert ext.requests == []  # the extension was never asked for a token


@pytest.mark.parametrize("request_, message", [
    ({"url": "https://evil.test/en/concert/1"}, "digitalconcerthall.com"),
    ({"url": URL, "item": 0}, "positive integer"),
    ({"url": URL, "item": True}, "positive integer"),
    ({"url": URL, "mode": "rm -rf"}, "mode must be"),
    ({"op": "other"}, "unknown operation"),
])
def test_bad_requests_are_rejected_before_asking_for_a_token(state, request_, message):
    ext = FakeExtension(lambda m: {"token": make_token(), "url": URL})
    request = {"secret": ext.host.secret, "op": "start", **request_}
    response = ext.host.handle_request(request)
    assert response["ok"] is False and message in response["error"]
    assert ext.requests == []


def test_extension_errors_and_missing_token_are_reported(state):
    ext = FakeExtension(lambda m: {"error": "2 concert pages are open; say which one by giving its URL."})
    answer = ext.host.handle_request({"secret": ext.host.secret, "op": "start"})
    assert answer["ok"] is False and "2 concert pages" in answer["error"]
    ext = FakeExtension(lambda m: {"token": None})
    answer = ext.host.handle_request({"secret": ext.host.secret, "op": "start", "url": URL})
    assert "Not signed in" in answer["error"]


def test_expired_token_is_refused(state):
    ext = FakeExtension(lambda m: {"token": make_token(-60), "url": URL})
    answer = ext.host.handle_request({"secret": ext.host.secret, "op": "start", "url": URL})
    assert answer["ok"] is False and "expired" in answer["error"]


def test_silent_extension_times_out(state, monkeypatch):
    monkeypatch.setattr(host, "TOKEN_WAIT_SECONDS", 0.3)
    ext = FakeExtension(lambda m: None)
    answer = ext.host.handle_request({"secret": ext.host.secret, "op": "start", "url": URL})
    assert answer["ok"] is False and "did not answer" in answer["error"]


def test_control_socket_end_to_end(state):
    token = make_token()
    ext = FakeExtension(lambda m: {"token": token, "url": URL})
    ext.host.worker_command = stub_worker(state)
    ext.host.serve_control()
    try:
        info = json.loads(host.bridge_file().read_text())
        assert set(info) == {"port", "secret", "pid"} and info["secret"] == ext.host.secret
        response = host.bridge_request({"op": "start", "url": URL})
        assert response["ok"] and response["job_id"] and "token" not in json.dumps(response)
        assert host.bridge_request({"op": "ping"})["ok"]
    finally:
        ext.host._server.shutdown()


def test_bridge_client_reports_missing_bridge(state):
    answer = host.bridge_request({"op": "ping"})
    assert answer["ok"] is False and "Brave bridge is not running" in answer["error"]


def test_host_main_rejects_unknown_caller_origin(state):
    assert host.main(["chrome-extension://abcdefghijklmnopabcdefghijklmnop/"]) == 2


def test_host_removes_bridge_file_when_browser_closes(state):
    reader, writer = os.pipe()
    h = host.Host(os.fdopen(reader, "rb"), io.BytesIO())
    thread = threading.Thread(target=h.run)
    thread.start()
    deadline = time.time() + 5
    while not host.bridge_file().exists() and time.time() < deadline:
        time.sleep(0.05)
    assert host.bridge_file().exists()
    os.close(writer)  # browser closes the pipe
    thread.join(5)
    assert not host.bridge_file().exists()


def test_extension_id_matches_manifest_key():
    import base64
    import hashlib
    from pathlib import Path

    manifest = json.loads((Path(__file__).resolve().parents[1] / "extensions" / "dch-bridge" / "manifest.json").read_text())
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    derived = "".join(chr(ord("a") + int(c, 16)) for c in digest)
    assert derived == host.EXTENSION_ID
    assert manifest["host_permissions"] == ["https://www.digitalconcerthall.com/*"]
    assert "tabs" not in manifest["permissions"]
