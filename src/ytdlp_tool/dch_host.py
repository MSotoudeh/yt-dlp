"""Native Messaging host: the only place the browser token and the local download worker meet.

Data flow (the access token never leaves this chain, and is never logged or returned to a client):

    MCP server / CLI --(loopback + secret: "start this URL")--> this host
    this host --(native messaging: "get_token")--> Brave extension (reads the site's own localStorage)
    extension --(token)--> this host --(stdin of a new detached process)--> download worker

The host is started by the browser when the extension connects. It also opens a loopback-only,
secret-protected control socket so local tools (the MCP server) can ask for downloads without ever
handling credentials. See docs/digital-concert-hall.md.
"""
from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import socketserver
import struct
import sys
import threading
from typing import BinaryIO

from . import dch, dch_jobs

HOST_NAME = "com.ytdlp_tool.dch"
MAX_REQUEST_BYTES = 64 * 1024
TOKEN_WAIT_SECONDS = 20


def bridge_file() -> Path:
    return dch_jobs.state_dir() / "dch-bridge.json"


def log(message: str) -> None:
    """Host log (stdout is reserved for the browser protocol). Never pass tokens."""
    try:
        path = dch_jobs.state_dir() / "host.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:
            path.replace(path.with_suffix(".log.1"))
        import time
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


# --- Native Messaging framing ------------------------------------------------

def read_message(stream: BinaryIO) -> dict | None:
    header = stream.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack("<I", header)
    if length > 16 * 1024 * 1024:
        raise ValueError("native message too large")
    body = stream.read(length)
    if len(body) < length:
        return None
    return json.loads(body.decode("utf-8"))


def write_message(stream: BinaryIO, message: dict) -> None:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(body)) + body)
    stream.flush()


# --- Host --------------------------------------------------------------------

class Host:
    def __init__(self, stdin: BinaryIO, stdout: BinaryIO, *, allowed_origin: str | None = None,
                 worker_command: list[str] | None = None, root: Path | None = None) -> None:
        self.stdin, self.stdout = stdin, stdout
        self.allowed_origin = allowed_origin
        self.worker_command = worker_command
        self.root = root
        self.secret = secrets.token_hex(32)
        self._write_lock = threading.Lock()
        self._next_id = 0
        self._id_lock = threading.Lock()
        self._pending: dict[int, queue.Queue] = {}
        self._server: socketserver.ThreadingTCPServer | None = None

    # extension side ---------------------------------------------------------
    def _send(self, message: dict) -> None:
        with self._write_lock:
            write_message(self.stdout, message)

    def request_token(self, url: str | None) -> dict:
        """Ask the extension for the token of a matching DCH tab. Returns {'token','url'} or {'error'}."""
        with self._id_lock:
            self._next_id += 1
            request_id = self._next_id
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._pending[request_id] = reply
        try:
            self._send({"id": request_id, "type": "get_token", "url": url})
            return reply.get(timeout=TOKEN_WAIT_SECONDS)
        except queue.Empty:
            return {"error": "The browser extension did not answer. Is Brave open with the extension enabled?"}
        finally:
            self._pending.pop(request_id, None)

    def pump(self) -> None:
        """Read messages from the extension until the browser closes the pipe."""
        while True:
            try:
                message = read_message(self.stdin)
            except (ValueError, json.JSONDecodeError, OSError) as exc:
                log(f"bad native message: {type(exc).__name__}")
                return
            if message is None:
                return
            target = self._pending.get(message.get("id")) if isinstance(message, dict) else None
            if target is not None:
                try:
                    target.put_nowait(message)
                except queue.Full:
                    pass

    # control side -----------------------------------------------------------
    def handle_request(self, request: dict) -> dict:
        if not isinstance(request, dict) or not hmac.compare_digest(str(request.get("secret", "")), self.secret):
            return {"ok": False, "error": "unauthorized"}
        op = request.get("op")
        if op == "ping":
            return {"ok": True}
        if op != "start":
            return {"ok": False, "error": "unknown operation"}
        url = request.get("url")
        mode = request.get("mode") or "download"
        item = request.get("item")
        if url is not None:
            try:
                url = dch.validate_dch_url(str(url))
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}
        if item is not None and (not isinstance(item, int) or isinstance(item, bool) or item < 1):
            return {"ok": False, "error": "item must be a positive integer"}
        if mode not in {"download", "list"}:
            return {"ok": False, "error": "mode must be 'download' or 'list'"}

        answer = self.request_token(url)
        if answer.get("error"):
            return {"ok": False, "error": str(answer["error"])[:300]}
        token, tab_url = answer.get("token"), answer.get("url")
        if not isinstance(token, str) or not token:
            return {"ok": False, "error": "Not signed in to Digital Concert Hall in this browser (no access token found)."}
        try:
            status = dch_jobs.start_job(
                str(tab_url or url), token, mode=mode, item=item,
                format_selector=str(request.get("format_selector") or dch.DEFAULT_FORMAT),
                worker_command=self.worker_command, root=self.root,
            )
        except (ValueError, dch.DchError) as exc:
            return {"ok": False, "error": dch._scrub(str(exc), token)[:300]}
        finally:
            token = ""  # drop our reference as early as possible
        return {"ok": True, **{k: status.get(k) for k in
                               ("job_id", "state", "mode", "url", "started_at", "duplicate", "already_done", "error")}}

    def serve_control(self) -> None:
        host = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                try:
                    raw = self.rfile.readline(MAX_REQUEST_BYTES)
                    response = host.handle_request(json.loads(raw.decode("utf-8")))
                except Exception as exc:  # a bad client must not take the host down
                    response = {"ok": False, "error": f"bad request ({type(exc).__name__})"}
                self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = False
            daemon_threads = True

        self._server = Server(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        path = bridge_file()
        dch_jobs.write_json_atomic(path, {"port": port, "secret": self.secret, "pid": os.getpid()})
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def run(self) -> int:
        self.serve_control()
        log("host started")
        try:
            self.pump()
        finally:
            if self._server:
                self._server.shutdown()
            try:
                info = json.loads(bridge_file().read_text(encoding="utf-8"))
                if info.get("pid") == os.getpid():
                    bridge_file().unlink()
            except (OSError, ValueError):
                pass
            log("host stopped")
        return 0


def bridge_request(request: dict, timeout: float = TOKEN_WAIT_SECONDS + 10) -> dict:
    """Client side (MCP server / CLI): talk to the running host. Never sees the token."""
    try:
        info = json.loads(bridge_file().read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=5) as conn:
            conn.settimeout(timeout)
            conn.sendall((json.dumps({**request, "secret": info["secret"]}) + "\n").encode("utf-8"))
            line = conn.makefile("rb").readline(MAX_REQUEST_BYTES)
        return json.loads(line.decode("utf-8"))
    except (OSError, ValueError, KeyError):
        return {"ok": False, "error": "The Brave bridge is not running. Open Brave with the "
                                      "'YTDLP Digital Concert Hall bridge' extension enabled."}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    origin = next((a for a in args if a.startswith("chrome-extension://")), None)
    expected = os.environ.get("YTDLP_DCH_EXTENSION_ORIGIN") or EXTENSION_ORIGIN
    if origin is not None and origin != expected:
        log("rejected unexpected caller origin")
        return 2
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    return Host(sys.stdin.buffer, sys.stdout.buffer, allowed_origin=expected).run()


# Deterministic ID derived from the public key in extensions/dch-bridge/manifest.json.
EXTENSION_ID = "bcohebdjklmiaddlkbemjfioeloajdlj"
EXTENSION_ORIGIN = f"chrome-extension://{EXTENSION_ID}/"

if __name__ == "__main__":
    raise SystemExit(main())
