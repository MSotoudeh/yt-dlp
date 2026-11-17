# Changelog

## 0.4.0 - 2026-11-17

### Added
- `ytdlp-tool dch` – download Digital Concert Hall content with your own short-lived access token
  (hidden prompt or `--token-stdin`; token kept in memory only; `--list`, `--item`). See
  `docs/digital-concert-hall.md`.
- Telegram bot: `--log-file`, job lifecycle logging, crash tracebacks in the log, and a launcher that
  writes `bot.log` / `bot.out.log` / `bot.stderr.log` with rotation.
- `scripts/Install-BotTask.ps1` to register or repair the scheduled task with robust restart settings.
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
