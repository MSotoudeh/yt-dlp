"""Minimal MCP server (stdio, JSON-RPC 2.0) exposing Digital Concert Hall jobs to AI clients.

Deliberately narrow (see docs/digital-concert-hall.md):

* ``dch_start``  – ask the local Brave bridge to start a download or an inspection (mutating).
* ``dch_status`` – read one job's status file (read-only).
* ``dch_jobs``   – list recent jobs (read-only).

There is no tool that runs arbitrary commands, reads arbitrary files or returns credentials. The
access token never passes through this process: the bridge hands it to the worker directly.
Implemented without third-party packages so it works from the bot/ASR virtual environment too.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from . import dch, dch_host, dch_jobs

SERVER_INFO = {"name": "ytdlp-tool-dch", "version": "1.0.0"}
DEFAULT_PROTOCOL = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "dch_start",
        "description": (
            "Start a Digital Concert Hall job on this computer using the user's signed-in Brave session. "
            "mode 'list' only inspects items and quality; mode 'download' saves the video files. "
            "Pass url, or omit it to use the single open concert/film page. Returns a job_id; the "
            "download may take many minutes, so do not wait: report the job_id and check dch_status "
            "only when the user asks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "https://www.digitalconcerthall.com/<lang>/(concert|film|work)/<id>"},
                "mode": {"type": "string", "enum": ["download", "list"], "default": "download"},
                "item": {"type": "integer", "minimum": 1, "description": "Only this 1-based part of a concert"},
            },
            "additionalProperties": False,
        },
        "annotations": {"title": "Start Digital Concert Hall job", "readOnlyHint": False,
                        "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "dch_status",
        "description": "Status of a job: state running/done/failed, saved file paths, or a sanitized error.",
        "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}},
                        "required": ["job_id"], "additionalProperties": False},
        "annotations": {"title": "Digital Concert Hall job status", "readOnlyHint": True,
                        "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "dch_jobs",
        "description": "List the most recent Digital Concert Hall jobs.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                        "additionalProperties": False},
        "annotations": {"title": "Recent Digital Concert Hall jobs", "readOnlyHint": True,
                        "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one tool; returns an MCP tool result. Errors are reported as tool errors, not exceptions."""
    try:
        if name == "dch_start":
            request = {"op": "start", "url": arguments.get("url"),
                       "mode": arguments.get("mode") or "download", "item": arguments.get("item")}
            response = dch_host.bridge_request(request)
            if not response.get("ok"):
                return _result({"error": response.get("error", "failed")}, error=True)
            response.pop("ok", None)
            return _result(response)
        if name == "dch_status":
            return _result(_public(dch_jobs.read_status(str(arguments.get("job_id", "")))))
        if name == "dch_jobs":
            limit = arguments.get("limit", 20)
            return _result({"jobs": dch_jobs.list_jobs(limit if isinstance(limit, int) and 0 < limit <= 50 else 20)})
    except (ValueError, dch.DchError, OSError) as exc:
        return _result({"error": str(exc)[:300]}, error=True)
    return _result({"error": f"Unknown tool {name}"}, error=True)


def _public(status: dict[str, Any]) -> dict[str, Any]:
    """Only fields meant for the client; the worker pid and internals stay local."""
    return {k: status.get(k) for k in
            ("job_id", "state", "mode", "url", "started_at", "finished_at", "error", "files", "result")}


def _result(payload: dict[str, Any], *, error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": error}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC message; returns the response, or None for notifications."""
    method, request_id = message.get("method"), message.get("id")
    params = message.get("params") or {}
    if request_id is None:
        return None  # notification (e.g. notifications/initialized)

    def ok(result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "initialize":
        return ok({"protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                   "capabilities": {"tools": {"listChanged": False}}, "serverInfo": SERVER_INFO})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        arguments = params.get("arguments")
        return ok(call_tool(str(params.get("name", "")), arguments if isinstance(arguments, dict) else {}))
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve(stdin=None, stdout=None) -> int:
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            response = handle(message) if isinstance(message, dict) else None
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
