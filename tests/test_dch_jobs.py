import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

import ytdlp_tool.dch as dch
import ytdlp_tool.dch_jobs as jobs
from test_dch import make_token

URL = "https://www.digitalconcerthall.com/en/concert/56205"


@pytest.fixture(autouse=True)
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_DCH_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("YTDLP_DCH_OUTPUT", str(tmp_path / "out"))
    return tmp_path


def stub_worker(tmp_path, body):
    """A worker stand-in: reads the token line from stdin like the real worker."""
    script = "import sys,time\ntoken = sys.stdin.readline().strip()\n" + body
    return [sys.executable, "-c", script, str(tmp_path)]


def test_job_id_is_stable_and_validates_url():
    a = jobs.make_job_id(URL, "download", None, "bv*+ba/b")
    assert a == jobs.make_job_id(URL + "/?x=1", "download", None, "bv*+ba/b")
    assert a != jobs.make_job_id(URL, "download", 2, "bv*+ba/b")
    with pytest.raises(ValueError):
        jobs.make_job_id("https://evil.test/en/concert/1", "download", None, "x")


def test_start_job_passes_token_only_on_stdin(state):
    token = make_token()
    worker = stub_worker(state, "open(sys.argv[1] + '/received', 'w').write(token)\n")
    status = jobs.start_job(URL, token, worker_command=worker)
    assert status["state"] == "running" and status["pid"]
    deadline = time.time() + 10
    while not (state / "received").exists() and time.time() < deadline:
        time.sleep(0.05)
    assert (state / "received").read_text() == token  # arrived via stdin
    for path in (state / "state").rglob("*"):  # ... and is written nowhere in the job files
        if path.is_file():
            assert token not in path.read_text(encoding="utf-8")


def test_start_job_rejects_bad_input(state):
    with pytest.raises(ValueError):
        jobs.start_job("https://evil.test/en/concert/1", make_token(), worker_command=["true"])
    with pytest.raises(dch.DchError, match="expired"):
        jobs.start_job(URL, make_token(-5), worker_command=["true"])
    with pytest.raises(ValueError):
        jobs.start_job(URL, make_token(), mode="rm -rf", worker_command=["true"])


def test_identical_running_job_is_not_started_twice(state):
    token = make_token()
    first = jobs.start_job(URL, token, worker_command=stub_worker(state, "time.sleep(3)\n"))
    second = jobs.start_job(URL, token, worker_command=stub_worker(state, "raise SystemExit('must not run')\n"))
    assert second["job_id"] == first["job_id"] and second["duplicate"] is True


def test_dead_worker_is_reported_failed_not_running(state):
    token = make_token()
    status = jobs.start_job(URL, token, worker_command=stub_worker(state, "pass\n"))
    deadline = time.time() + 10
    while jobs.pid_alive(status["pid"]) and time.time() < deadline:
        time.sleep(0.05)
    seen = jobs.read_status(status["job_id"])
    assert seen["state"] == "failed" and "no longer running" in seen["error"]


def test_worker_failure_to_launch_is_recorded(state):
    status = jobs.start_job(URL, make_token(), worker_command=["/definitely/not/a/program"])
    assert status["state"] == "failed" and "Could not start" in status["error"]


def test_run_worker_download_success(state, monkeypatch):
    token = make_token()
    media = state / "out" / "a" / "01 - X.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"data")
    monkeypatch.setattr(dch, "download", lambda *a, **k: dch.DchDownload(paths=(media,), items=2))
    spec = {"job_id": "abc123", "url": URL, "mode": "download", "item": None,
            "format_selector": "x", "output_dir": str(state / "out"), "timeout_seconds": 60}
    job_dir = state / "jobs" / "abc123"
    jobs.write_json_atomic(job_dir / "job.json", spec)
    assert jobs.run_worker(job_dir, io.StringIO(token + "\n")) == 0
    status = json.loads((job_dir / "status.json").read_text())
    assert status["state"] == "done" and status["files"] == [str(media)] and status["finished_at"]
    assert token not in (job_dir / "status.json").read_text()


def test_run_worker_never_marks_empty_output_done(state, monkeypatch):
    empty = state / "out" / "empty.mp4"
    empty.parent.mkdir(parents=True)
    empty.write_bytes(b"")
    monkeypatch.setattr(dch, "download", lambda *a, **k: dch.DchDownload(paths=(empty,), items=1))
    spec = {"job_id": "abc124", "url": URL, "mode": "download", "item": None,
            "format_selector": "x", "output_dir": str(state / "out"), "timeout_seconds": 60}
    job_dir = state / "jobs" / "abc124"
    jobs.write_json_atomic(job_dir / "job.json", spec)
    assert jobs.run_worker(job_dir, io.StringIO(make_token() + "\n")) == 1
    assert json.loads((job_dir / "status.json").read_text())["state"] == "failed"


def test_run_worker_scrubs_token_from_errors(state, monkeypatch):
    token = make_token()

    def boom(*a, **k):
        raise dch.DchError(f"server said no to {token}")

    monkeypatch.setattr(dch, "list_items", boom)
    spec = {"job_id": "abc125", "url": URL, "mode": "list", "item": None,
            "format_selector": "x", "output_dir": str(state / "out"), "timeout_seconds": 60}
    job_dir = state / "jobs" / "abc125"
    jobs.write_json_atomic(job_dir / "job.json", spec)
    assert jobs.run_worker(job_dir, io.StringIO(token + "\n")) == 1
    text = (job_dir / "status.json").read_text()
    assert token not in text and "***" in text


def test_run_worker_without_token_fails_cleanly(state):
    spec = {"job_id": "abc126", "url": URL, "mode": "list", "item": None,
            "format_selector": "x", "output_dir": str(state / "out"), "timeout_seconds": 60}
    job_dir = state / "jobs" / "abc126"
    jobs.write_json_atomic(job_dir / "job.json", spec)
    assert jobs.run_worker(job_dir, io.StringIO("")) == 1
    assert "did not receive an access token" in json.loads((job_dir / "status.json").read_text())["error"]


def test_worker_timeout_marks_failed_and_removes_partials(state, tmp_path):
    out = state / "out"
    out.mkdir()
    spec = {"job_id": "abc127", "url": URL, "mode": "download", "item": None,
            "format_selector": "x", "output_dir": str(out), "timeout_seconds": 1}
    job_dir = state / "jobs" / "abc127"
    jobs.write_json_atomic(job_dir / "job.json", spec)
    program = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "import ytdlp_tool.dch as dch, ytdlp_tool.dch_jobs as jobs\n"
        "def slow(*a, **k):\n"
        f"    Path({str(out / 'x.mp4.part')!r}).write_bytes(b'partial')\n"
        "    time.sleep(30)\n"
        "dch.download = slow\n"
        f"sys.exit(jobs.run_worker({str(job_dir)!r}))\n"
    )
    proc = subprocess.run([sys.executable, "-c", program], input=make_token() + "\n", text=True, timeout=20,
                          env={**os.environ, "PYTHONPATH": str(Path(jobs.__file__).parents[1])})
    assert proc.returncode == 1
    status = json.loads((job_dir / "status.json").read_text())
    assert status["state"] == "failed" and "Timed out" in status["error"]
    assert not (out / "x.mp4.part").exists()


def test_status_validation_and_listing(state):
    with pytest.raises(ValueError):
        jobs.read_status("../../etc")
    with pytest.raises(dch.DchError, match="Unknown job"):
        jobs.read_status("abcdef")
    jobs.write_json_atomic(jobs.jobs_root() / "abcdef" / "status.json",
                           {"job_id": "abcdef", "state": "done", "mode": "list", "url": URL})
    assert [j["job_id"] for j in jobs.list_jobs()] == ["abcdef"]


def test_pid_alive():
    assert jobs.pid_alive(os.getpid())
    assert not jobs.pid_alive(None) and not jobs.pid_alive(0)
