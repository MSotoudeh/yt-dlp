"""Background Digital Concert Hall jobs: file-based state, one detached worker per job.

Design (see docs/digital-concert-hall.md):

* A job is a directory ``<jobs root>/<job id>/`` holding ``job.json`` (the request, never a token)
  and ``status.json`` (pid, times, state, sanitized error, finished files).
* The worker is a detached process that reads the access token from **stdin** (not argv, not the
  environment, not a file), runs the download, enforces its own timeout, and records the outcome.
* A job is only ``done`` after every reported file exists and is non-empty; partial files or a
  dead worker are reported as ``failed``, never as success.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

from . import dch

DEFAULT_TIMEOUT_SECONDS = 6 * 3600
STATES = ("running", "done", "failed")


def _repo_root() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").is_file() else None


def default_output_dir() -> Path:
    """Where downloads go: $YTDLP_DCH_OUTPUT, else <repo>/output/chatgpt/digital-concert-hall."""
    override = os.environ.get("YTDLP_DCH_OUTPUT")
    if override:
        return Path(override).expanduser().resolve()
    root = _repo_root()
    base = root / "output" if root else Path.home() / ".ytdlp-tool"
    return base / "chatgpt" / "digital-concert-hall"


def state_dir() -> Path:
    """Per-user directory for the bridge file and job state (outside the repo)."""
    override = os.environ.get("YTDLP_DCH_STATE")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "state") / "ytdlp-tool" / "dch"


def jobs_root() -> Path:
    return state_dir() / "jobs"


def make_job_id(url: str, mode: str, item: int | None, format_selector: str) -> str:
    key = "|".join([dch.validate_dch_url(url), mode, str(item or 0), format_selector])
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def pid_alive(pid: int | None) -> bool:
    """Is the process alive? (os.kill(pid, 0) would TERMINATE the process on Windows, so avoid it.)"""
    if not pid or pid < 1:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # an exited-but-unreaped child is a zombie, not a running worker
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def read_status(job_id: str, root: Path | None = None) -> dict[str, Any]:
    """Current status of a job; a 'running' job whose worker died is reported as failed."""
    if not job_id or not all(c in "0123456789abcdef" for c in job_id):
        raise ValueError("Invalid job id")
    path = (root or jobs_root()) / job_id / "status.json"
    if not path.is_file():
        raise dch.DchError(f"Unknown job {job_id}")
    status = json.loads(path.read_text(encoding="utf-8"))
    if status.get("state") == "running" and not pid_alive(status.get("pid")):
        status = {**status, "state": "failed", "finished_at": status.get("finished_at") or _iso(_now()),
                  "error": status.get("error") or "The worker process is no longer running (it crashed or was killed)."}
    return status


def list_jobs(limit: int = 20, root: Path | None = None) -> list[dict[str, Any]]:
    base = root or jobs_root()
    if not base.is_dir():
        return []
    entries = sorted((p for p in base.iterdir() if (p / "status.json").is_file()),
                     key=lambda p: (p / "status.json").stat().st_mtime, reverse=True)
    out = []
    for path in entries[:limit]:
        try:
            status = read_status(path.name, base)
        except (OSError, ValueError, dch.DchError):
            continue
        out.append({k: status.get(k) for k in ("job_id", "state", "mode", "url", "started_at", "finished_at", "error")})
    return out


def start_job(
    url: str,
    token: str,
    *,
    mode: str = "download",
    item: int | None = None,
    format_selector: str = dch.DEFAULT_FORMAT,
    output_dir: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    root: Path | None = None,
    worker_command: list[str] | None = None,
) -> dict[str, Any]:
    """Validate, create the job and launch a detached worker that receives the token on stdin.

    Returns the status dict. An identical running job is not started twice; an identical finished
    job returns its result (``already_done``).
    """
    if mode not in {"download", "list"}:
        raise ValueError("mode must be 'download' or 'list'")
    url = dch.validate_dch_url(url)
    if item is not None and item < 1:
        raise ValueError("item must be 1 or greater")
    dch.token_seconds_left(token)  # fail fast on an expired/garbled token
    job_id = make_job_id(url, mode, item, format_selector)
    job_dir = (root or jobs_root()) / job_id

    if (job_dir / "status.json").is_file():
        existing = read_status(job_id, root)
        if existing["state"] == "running":
            return {**existing, "duplicate": True}
        if existing["state"] == "done" and mode == "download":
            return {**existing, "already_done": True}

    spec = {
        "job_id": job_id, "url": url, "mode": mode, "item": item,
        "format_selector": format_selector,
        "output_dir": str((output_dir or default_output_dir()).resolve()),
        "timeout_seconds": int(timeout_seconds),
    }
    write_json_atomic(job_dir / "job.json", spec)
    queued = {"job_id": job_id, "state": "running", "mode": mode, "url": url, "pid": None,
              "started_at": _iso(_now()), "finished_at": None, "error": None, "files": [], "result": None,
              "expected_seconds": None}
    write_json_atomic(job_dir / "status.json", queued)

    command = worker_command or [sys.executable, "-m", "ytdlp_tool", "dch-worker", str(job_dir)]
    kwargs: dict[str, Any] = {"stdin": subprocess.PIPE, "stdout": subprocess.DEVNULL,
                              "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(command, **kwargs)  # noqa: S603 - fixed argv, no user input
        assert proc.stdin is not None
        proc.stdin.write((token + "\n").encode())
        proc.stdin.close()
    except OSError as exc:
        failed = {**queued, "state": "failed", "finished_at": _iso(_now()),
                  "error": f"Could not start the worker: {type(exc).__name__}"}
        write_json_atomic(job_dir / "status.json", failed)
        return failed
    threading.Thread(target=proc.wait, daemon=True).start()  # reap the child so it never lingers as a zombie
    queued["pid"] = proc.pid
    write_json_atomic(job_dir / "status.json", queued)
    return queued


def run_worker(job_dir: str | Path, stdin=None) -> int:
    """Worker entry point: token from stdin, state in status.json. Returns the process exit code."""
    job_dir = Path(job_dir)
    stream = stdin if stdin is not None else sys.stdin
    token = (stream.readline() or "").strip()
    spec = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    status_path = job_dir / "status.json"
    started = _now()
    status: dict[str, Any] = {
        "job_id": spec["job_id"], "state": "running", "mode": spec["mode"], "url": spec["url"],
        "pid": os.getpid(), "started_at": _iso(started), "finished_at": None, "error": None,
        "files": [], "result": None, "expected_seconds": spec["timeout_seconds"],
    }
    write_json_atomic(status_path, status)
    output_dir = Path(spec["output_dir"])

    def finish(state: str, *, error: str | None = None, files=(), result=None) -> None:
        final = {**status, "state": state, "finished_at": _iso(_now()), "error": error,
                 "files": [str(p) for p in files], "result": result}
        write_json_atomic(status_path, final)

    def on_timeout() -> None:
        _remove_partials(output_dir, since=started)
        finish("failed", error=f"Timed out after {spec['timeout_seconds']} s; partial files were removed.")
        os._exit(1)

    watchdog = threading.Timer(spec["timeout_seconds"], on_timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        if not token:
            raise dch.DchError("The worker did not receive an access token.")
        if spec["mode"] == "list":
            items = dch.list_items(spec["url"], token)
            result = [{"index": i.index, "id": i.video_id, "title": i.title, "duration": i.duration,
                       "formats": i.formats, "best_height": i.best_height} for i in items]
            finish("done", result=result)
        else:
            outcome = dch.download(spec["url"], token, output_dir, item=spec["item"],
                                   format_selector=spec["format_selector"])
            missing = [p for p in outcome.paths if not p.is_file() or p.stat().st_size == 0]
            if missing:
                raise dch.DchError("A reported output file is missing or empty; not marking the job done.")
            finish("done", files=outcome.paths, result={"items": outcome.items})
        return 0
    except (dch.DchError, ValueError) as exc:
        finish("failed", error=dch._scrub(str(exc), token)[:400])
    except Exception as exc:  # never leave a job 'running' forever
        finish("failed", error=f"Unexpected {type(exc).__name__}: {dch._scrub(str(exc), token)[:300]}")
    finally:
        watchdog.cancel()
    return 1


def _remove_partials(directory: Path, *, since: float) -> None:
    if not directory.is_dir():
        return
    for path in directory.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in {".part", ".ytdl", ".temp"} and path.stat().st_mtime >= since - 5:
                path.unlink()
        except OSError:
            pass
