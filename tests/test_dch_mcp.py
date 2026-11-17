import io
import json

import pytest

import ytdlp_tool.dch_host as host
import ytdlp_tool.dch_jobs as jobs
import ytdlp_tool.dch_mcp as mcp

URL = "https://www.digitalconcerthall.com/en/concert/56205"


@pytest.fixture(autouse=True)
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_DCH_STATE", str(tmp_path / "state"))


def rpc(method, params=None, request_id=1):
    return mcp.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})


def payload(response):
    return json.loads(response["result"]["content"][0]["text"])


def test_initialize_and_tool_listing():
    init = rpc("initialize", {"protocolVersion": "2025-03-26"})
    assert init["result"]["protocolVersion"] == "2025-03-26" and "tools" in init["result"]["capabilities"]
    names = [t["name"] for t in rpc("tools/list")["result"]["tools"]]
    assert names == ["dch_start", "dch_status", "dch_jobs"]
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert rpc("nope")["error"]["code"] == -32601
    assert rpc("ping")["result"] == {}


def test_tools_never_accept_or_return_credentials():
    for tool in mcp.TOOLS:
        assert not {"token", "password", "cookie", "authorization"} & set(tool["inputSchema"]["properties"])
        assert tool["inputSchema"]["additionalProperties"] is False
    annotations = {t["name"]: t["annotations"] for t in mcp.TOOLS}
    assert annotations["dch_start"]["readOnlyHint"] is False  # starting a download is a mutation
    assert annotations["dch_status"]["readOnlyHint"] and annotations["dch_jobs"]["readOnlyHint"]


def test_start_goes_through_the_bridge_without_a_token(monkeypatch):
    seen = {}

    def fake_bridge(request):
        seen.update(request)
        return {"ok": True, "job_id": "abc123", "state": "running"}

    monkeypatch.setattr(host, "bridge_request", fake_bridge)
    result = rpc("tools/call", {"name": "dch_start", "arguments": {"url": URL, "mode": "list"}})
    assert payload(result) == {"job_id": "abc123", "state": "running"}
    assert seen == {"op": "start", "url": URL, "mode": "list", "item": None}


def test_start_reports_bridge_errors_as_tool_errors(monkeypatch):
    monkeypatch.setattr(host, "bridge_request", lambda r: {"ok": False, "error": "bridge down"})
    result = rpc("tools/call", {"name": "dch_start", "arguments": {}})
    assert result["result"]["isError"] is True and payload(result)["error"] == "bridge down"


def test_status_hides_internal_fields_and_validates_ids():
    jobs.write_json_atomic(jobs.jobs_root() / "abc123" / "status.json", {
        "job_id": "abc123", "state": "done", "mode": "download", "url": URL, "pid": 99999999,
        "files": ["C:/x/01.mp4"], "result": {"items": 1}, "error": None,
        "started_at": "t0", "finished_at": "t1",
    })
    status = payload(rpc("tools/call", {"name": "dch_status", "arguments": {"job_id": "abc123"}}))
    assert status["state"] == "done" and status["files"] == ["C:/x/01.mp4"] and "pid" not in status
    bad = rpc("tools/call", {"name": "dch_status", "arguments": {"job_id": "../x"}})
    assert bad["result"]["isError"] is True
    unknown = rpc("tools/call", {"name": "shell", "arguments": {"cmd": "dir"}})
    assert unknown["result"]["isError"] is True
    assert payload(rpc("tools/call", {"name": "dch_jobs", "arguments": {}}))["jobs"][0]["job_id"] == "abc123"


def test_stdio_loop_handles_garbage_lines():
    lines = "\n".join([
        "not json",
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "",
    ])
    out = io.StringIO()
    assert mcp.serve(io.StringIO(lines + "\n"), out) == 0
    responses = [json.loads(line) for line in out.getvalue().splitlines()]
    assert responses[0]["error"]["code"] == -32700
    assert responses[1] == {"jsonrpc": "2.0", "id": 7, "result": {}}
    assert len(responses) == 2
