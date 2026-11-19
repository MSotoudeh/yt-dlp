# Changelog

## 0.5.0 - 2026-11-17

### Added
- **Digital Concert Hall browser bridge** (plan `tasks/plan.md`, phases 3-5): a Manifest V3 Brave/Chromium extension
  (`extensions/dch-bridge`, domain-limited), a Native Messaging host (`dch_host`), detached background workers with
  file-based job state, timeouts and duplicate protection (`dch_jobs`), and CLI `dch-start` / `dch-status`.
- **MCP server** `ytdlp_tool.dch_mcp` (`dch_start`, `dch_status`, `dch_jobs`; no credentials in or out) and an installer
  `python -m ytdlp_tool.dch_install install|status|uninstall` that registers the host for Brave and adds the server to
  Claude Desktop and Codex configs (with backups). YTDL plugin 0.2.9 documents the workflow.
- `tests/e2e/run_dch_e2e.sh`: real Chromium + real extension + host + worker end-to-end test with a fake site/token.
- Tests for jobs, host, MCP and installer (245 tests total).

### Changed
- `dch` output now defaults to `output/chatgpt/digital-concert-hall`; URL validation normalizes trailing slashes.

## 0.4.0 - 2026-11-17

### Added
- `ytdlp-tool dch` – download Digital Concert Hall content with your own short-lived access token
  (hidden prompt or `--token-stdin`; token kept in memory only; `--list`, `--item`). See
  `docs/digital-concert-hall.md`.
- Telegram bot: `--log-file`, job lifecycle logging, crash tracebacks in the log, and a launcher that
  writes `bot.log` / `bot.out.log` / `bot.stderr.log` with rotation.
- `scripts/Install-BotTask.ps1` (renamed `scripts/install-bot-task.ps1` in 0.5.1) to register or repair the scheduled task with robust restart settings.
- `docs/operations.md`, `docs/digital-concert-hall.md`, `docs/digital-concert-hall-plan-review.md`.
- ruff configuration and `ruff` in the `dev` extra.

### Fixed
- Telegram bot died on any transient network error while polling; it now retries with backoff
  (the scheduled task previously gave up after 3 restarts, leaving the bot dead).
- A wildcard `YTDL_ALLOWED_CHAT_IDS=*` needs the explicit opt-in `YTDL_ALLOW_PUBLIC_BOT=1`.
- `ytdlp_tool.__version__` was stuck at 0.2.0 while `pyproject.toml` said 0.3.0; a test now keeps them equal.
- A test guard used `pytest` without importing it (it would have raised `NameError` instead of failing cleanly).
- Removed dead code (unused variable in `linkedin.py`, unreachable branches in the bot).

### Changed
- `telegram_bot.main()` (about 250 lines) split into small, testable functions (`dispatch_job`,
  `process_job`, `failure_notice`, `load_allowlist`, ...). Behaviour, commands and messages are unchanged.
- `yt-dlp>=2026.8.19` is now the minimum (site extractors break frequently).
- Unused imports/variables removed repo-wide; a side-effect `import torch` in the GPU benchmark script is kept on purpose.

## 0.3.0 and earlier

See git history: Whisper transcription (0.3), Instagram / X / LinkedIn post workflows, the Telegram bot,
transcript-first YouTube handling, and the Persian ASR benchmark documents under `docs/`.
