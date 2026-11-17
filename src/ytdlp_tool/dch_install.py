"""Installer for the Digital Concert Hall bridge on Windows (idempotent, reversible).

    python -m ytdlp_tool.dch_install install   [--python PY] [--browsers brave,chrome] [--no-claude] [--no-codex]
    python -m ytdlp_tool.dch_install status
    python -m ytdlp_tool.dch_install uninstall

It does four things, each with a backup of any file it edits:
1. writes the native-messaging host launcher + manifest under the per-user state directory;
2. registers that host for the chosen Chromium browsers (HKCU, no admin needed);
3. adds the ``ytdlp-dch`` MCP server to Claude Desktop's config;
4. adds ``[mcp_servers.ytdlp_dch]`` to Codex's ``config.toml``.

Loading the extension itself is a one-time manual browser step (see docs/digital-concert-hall.md).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

from . import dch_host, dch_jobs

MCP_NAME = "ytdlp-dch"
CODEX_TABLE = "mcp_servers.ytdlp_dch"
BACKUP_SUFFIX = ".bak-before-ytdlp-dch"
BROWSER_KEYS = {
    "brave": r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
    "chrome": r"Software\Google\Chrome\NativeMessagingHosts",
    "edge": r"Software\Microsoft\Edge\NativeMessagingHosts",
}


def repo_src() -> Path:
    return Path(__file__).resolve().parents[1]


def default_python() -> Path:
    venv = repo_src().parent / "output" / "chatgpt" / "asr-venv" / "Scripts" / "python.exe"
    return venv if venv.is_file() else Path(sys.executable)


def host_dir() -> Path:
    return dch_jobs.state_dir() / "native-host"


def launcher_text(python: Path, src: Path) -> str:
    """The .cmd the browser starts. Nothing may print to stdout: it is the native-messaging pipe."""
    return (
        "@echo off\r\n"
        f'set "PYTHONPATH={src}"\r\n'
        'set "PYTHONIOENCODING=utf-8"\r\n'
        f'"{python}" -m ytdlp_tool.dch_host %*\r\n'
    )


def manifest_dict(launcher: Path) -> dict:
    return {
        "name": dch_host.HOST_NAME,
        "description": "ytdlp-tool Digital Concert Hall bridge (hands the browser token to the local worker)",
        "path": str(launcher),
        "type": "stdio",
        "allowed_origins": [dch_host.EXTENSION_ORIGIN],
    }


def write_host_files(python: Path, src: Path | None = None) -> Path:
    directory = host_dir()
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "dch-host.cmd"
    launcher.write_bytes(launcher_text(python, src or repo_src()).encode("utf-8"))
    manifest = directory / f"{dch_host.HOST_NAME}.json"
    manifest.write_text(json.dumps(manifest_dict(launcher), indent=2), encoding="utf-8")
    return manifest


def server_spec(python: Path, src: Path | None = None) -> dict:
    return {"command": str(python), "args": ["-m", "ytdlp_tool.dch_mcp"], "env": {"PYTHONPATH": str(src or repo_src())}}


def _backup(path: Path) -> None:
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)


def merge_claude_config(path: Path, python: Path, src: Path | None = None) -> bool:
    """Add/update our MCP server in Claude Desktop's config; other entries are left untouched.

    Returns True if the file changed. A config that is not valid JSON is never modified.
    """
    config: dict = {}
    if path.exists():
        text = path.read_text(encoding="utf-8-sig")
        config = json.loads(text) if text.strip() else {}
        if not isinstance(config, dict):
            raise ValueError(f"{path} does not contain a JSON object")
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers is not an object")
    wanted = server_spec(python, src)
    if servers.get(MCP_NAME) == wanted:
        return False
    _backup(path)
    servers[MCP_NAME] = wanted
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def remove_claude_config(path: Path) -> bool:
    if not path.exists():
        return False
    config = json.loads(path.read_text(encoding="utf-8-sig") or "{}")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict) or MCP_NAME not in servers:
        return False
    _backup(path)
    del servers[MCP_NAME]
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def codex_block(python: Path, src: Path | None = None) -> str:
    # json.dumps output is a valid TOML basic string (escaped backslashes and quotes)
    return (
        f"\n[{CODEX_TABLE}]\n"
        f"command = {json.dumps(str(python))}\n"
        'args = ["-m", "ytdlp_tool.dch_mcp"]\n'
        f"env = {{ PYTHONPATH = {json.dumps(str(src or repo_src()))} }}\n"
    )


def ensure_codex_config(path: Path, python: Path, src: Path | None = None) -> bool:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if f"[{CODEX_TABLE}]" in text:
        return False
    _backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n" + codex_block(python, src), encoding="utf-8")
    return True


def remove_codex_config(path: Path) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, skipping, changed = [], False, False
    for line in lines:
        stripped = line.strip()
        if stripped == f"[{CODEX_TABLE}]":
            skipping, changed = True, True
            continue
        if skipping and stripped.startswith("["):
            skipping = False
        if not skipping:
            out.append(line)
    if changed:
        _backup(path)
        path.write_text("".join(out), encoding="utf-8")
    return changed


def register_browser(browser: str, manifest: Path) -> None:
    import winreg  # Windows only

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, BROWSER_KEYS[browser] + "\\" + dch_host.HOST_NAME) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))


def unregister_browser(browser: str) -> bool:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, BROWSER_KEYS[browser] + "\\" + dch_host.HOST_NAME)
        return True
    except FileNotFoundError:
        return False


def claude_config_path() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Claude" / "claude_desktop_config.json"


def codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ytdlp_tool.dch_install", description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=("install", "uninstall", "status"))
    parser.add_argument("--python", type=Path, default=None, help="Python used by the host and MCP server")
    parser.add_argument("--browsers", default="brave", help="comma list of: " + ",".join(BROWSER_KEYS))
    parser.add_argument("--no-claude", action="store_true")
    parser.add_argument("--no-codex", action="store_true")
    args = parser.parse_args(argv)
    browsers = [b.strip() for b in args.browsers.split(",") if b.strip()]
    unknown = [b for b in browsers if b not in BROWSER_KEYS]
    if unknown:
        parser.error("unknown browser: " + ", ".join(unknown))
    python = (args.python or default_python()).resolve()

    if args.action == "install":
        if os.name != "nt":
            parser.error("installation targets Windows (it registers a native-messaging host in HKCU)")
        manifest = write_host_files(python)
        print(f"host manifest: {manifest}")
        for browser in browsers:
            register_browser(browser, manifest)
            print(f"registered native host for {browser}")
        if not args.no_claude:
            print("Claude Desktop config:", "updated" if merge_claude_config(claude_config_path(), python) else "already set")
        if not args.no_codex:
            print("Codex config:", "updated" if ensure_codex_config(codex_config_path(), python) else "already set")
        print(f"\nExtension ID: {dch_host.EXTENSION_ID}")
        print("Next: load the unpacked extension in the browser and restart Claude Desktop / Codex.")
        return 0

    if args.action == "uninstall":
        if os.name == "nt":
            for browser in browsers:
                print(f"unregistered {browser}:", unregister_browser(browser))
        print("Claude Desktop entry removed:", remove_claude_config(claude_config_path()))
        print("Codex entry removed:", remove_codex_config(codex_config_path()))
        shutil.rmtree(host_dir(), ignore_errors=True)
        return 0

    manifest = host_dir() / f"{dch_host.HOST_NAME}.json"
    print("host manifest present:", manifest.is_file())
    print("bridge running (browser connected):", dch_host.bridge_request({"op": "ping"}).get("ok", False))
    print("extension ID:", dch_host.EXTENSION_ID)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
