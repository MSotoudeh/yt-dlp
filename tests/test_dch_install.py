import json
from pathlib import Path
import tomllib

import pytest

import ytdlp_tool.dch_host as host
import ytdlp_tool.dch_install as inst

PY = Path(r"C:\GitHub\yt-dlp\output\chatgpt\asr-venv\Scripts\python.exe")
SRC = Path(r"C:\GitHub\yt-dlp\src")


@pytest.fixture(autouse=True)
def state(monkeypatch, tmp_path):
    monkeypatch.setenv("YTDLP_DCH_STATE", str(tmp_path / "state"))


def test_launcher_is_silent_and_forwards_the_browser_origin():
    text = inst.launcher_text(PY, SRC)
    assert text.startswith("@echo off\r\n")  # nothing may be echoed into the native-messaging pipe
    assert f'"{PY}" -m ytdlp_tool.dch_host %*' in text
    assert f'set "PYTHONPATH={SRC}"' in text and "\n" not in text.replace("\r\n", "")


def test_host_manifest_only_allows_our_extension(tmp_path):
    manifest = json.loads(inst.write_host_files(PY, SRC).read_text())
    assert manifest["name"] == "com.ytdlp_tool.dch" and manifest["type"] == "stdio"
    assert manifest["allowed_origins"] == [f"chrome-extension://{host.EXTENSION_ID}/"]
    assert manifest["path"].endswith("dch-host.cmd") and Path(manifest["path"]).is_file()


def test_claude_config_merge_keeps_other_servers_and_is_idempotent(tmp_path):
    path = tmp_path / "claude_desktop_config.json"
    path.write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    assert inst.merge_claude_config(path, PY, SRC) is True
    config = json.loads(path.read_text())
    assert config["theme"] == "dark" and config["mcpServers"]["other"] == {"command": "x"}
    assert config["mcpServers"]["ytdlp-dch"]["args"] == ["-m", "ytdlp_tool.dch_mcp"]
    assert json.loads((tmp_path / ("claude_desktop_config.json" + inst.BACKUP_SUFFIX)).read_text())["theme"] == "dark"
    assert inst.merge_claude_config(path, PY, SRC) is False  # second run changes nothing
    assert inst.remove_claude_config(path) is True
    assert "ytdlp-dch" not in json.loads(path.read_text())["mcpServers"]
    assert inst.remove_claude_config(path) is False


def test_claude_config_creates_missing_file_and_refuses_garbage(tmp_path):
    fresh = tmp_path / "new" / "claude_desktop_config.json"
    assert inst.merge_claude_config(fresh, PY, SRC) is True and fresh.exists()
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        inst.merge_claude_config(broken, PY, SRC)
    assert broken.read_text() == "{not json"  # untouched
    listy = tmp_path / "list.json"
    listy.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        inst.merge_claude_config(listy, PY, SRC)


def test_codex_block_is_valid_toml_and_roundtrips(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('model = "gpt"\n\n[mcp_servers.keep]\ncommand = "k"\n', encoding="utf-8")
    assert inst.ensure_codex_config(path, PY, SRC) is True
    data = tomllib.loads(path.read_text())
    server = data["mcp_servers"]["ytdlp_dch"]
    assert server["command"] == str(PY) and server["env"]["PYTHONPATH"] == str(SRC)
    assert data["model"] == "gpt" and data["mcp_servers"]["keep"]["command"] == "k"
    assert inst.ensure_codex_config(path, PY, SRC) is False
    assert inst.remove_codex_config(path) is True
    after = tomllib.loads(path.read_text())
    assert "ytdlp_dch" not in after["mcp_servers"] and after["mcp_servers"]["keep"]["command"] == "k"


def test_codex_config_created_when_missing(tmp_path):
    path = tmp_path / ".codex" / "config.toml"
    assert inst.ensure_codex_config(path, PY, SRC) is True
    assert "ytdlp_dch" in tomllib.loads(path.read_text())["mcp_servers"]


def test_status_runs_without_a_bridge(capsys):
    assert inst.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "bridge running (browser connected): False" in out and host.EXTENSION_ID in out
