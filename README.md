# ytdlp-tool

A Python automation toolkit and private Telegram bot built **on top of** [yt-dlp](https://github.com/yt-dlp/yt-dlp) for transcripts, subtitles, media downloads and public social-media posts.

> **This is not the upstream yt-dlp project.** It is a separate, personal project (Python package `ytdlp-tool`) that uses yt-dlp as a library dependency. Report yt-dlp extractor bugs to [yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp), not here. The repository name `yt-dlp` is historical.

## Status

**Active, single maintainer.** Used daily on one Windows machine (called "Ops" in the docs) where the Telegram bot runs as a scheduled task. Version 0.5.0; see [CHANGELOG.md](CHANGELOG.md).

## What it does

- **YouTube text:** `transcript` returns the published caption track in the video's original spoken language and falls back to local Whisper speech recognition only when no such track exists. `subs` lists or downloads subtitles as VTT, SRT or TXT.
- **Media:** `info`, `formats`, `video`, `audio`, `thumbnail`, `playlist` (inspect by default, download only on request), `clip` (time range) and `comments`, for any site yt-dlp supports.
- **Speech to text:** `transcribe` turns a URL or local file into TXT and time-coded SRT with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), fully offline after the model download.
- **Public posts:** `ig-caption`, `ig-media`, `ig-speech`, `x-post` and `li-post` fetch the original photos, videos and author-written text of public Instagram, X/Twitter and LinkedIn posts, without logins, cookies or paid APIs.
- **Telegram bot:** a private, allowlisted long-polling bot that exposes the commands above to one chat ([docs/telegram-bot.md](docs/telegram-bot.md)).
- **Digital Concert Hall:** `dch`, `dch-start` and `dch-status` download concerts and films from your own [Digital Concert Hall](https://www.digitalconcerthall.com) account. The access token comes from your signed-in Brave browser through a small extension and a native-messaging host, and is never printed or stored. An MCP server lets Claude Desktop and Codex start and check those downloads ([docs/digital-concert-hall.md](docs/digital-concert-hall.md)).
- **ChatGPT plugin:** `plugins/ytdl/` is a skills-only plugin that tells ChatGPT how to call this toolkit on the Ops machine.

## How it works

```text
  ytdlp-tool CLI ──────────┐
  Telegram bot (polling) ──┤      src/ytdlp_tool/
  MCP server (dch_mcp) ────┤  ──►  cli.py → media / subtitles / transcript / transcribe
  ChatGPT plugin (skills) ─┘       instagram / x_twitter / linkedin     → yt-dlp, requests
                                   dch → dch_jobs (detached worker)      → yt-dlp, ffmpeg
  Brave extension ── native messaging ──► dch_host ──(stdin)──► dch worker
```

- `cli.py` routes every command; the workflow modules call the yt-dlp Python API (not the shell) so the same code serves the CLI, the bot and the MCP server.
- `telegram_bot.py` stores jobs in SQLite, runs one job at a time by calling the CLI in a subprocess, and uploads results with the Telegram Bot API.
- The Digital Concert Hall path keeps the token in memory only: extension → host → worker stdin. See the guide for the security model.

## Quick start

Requires Python 3.11+ and, for audio extraction, clipping, muxing and transcription, [ffmpeg](https://ffmpeg.org/) on `PATH`.

```powershell
git clone https://github.com/MSotoudeh/yt-dlp.git ytdlp-tool
cd ytdlp-tool
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\ytdlp-tool.exe --help
.venv\Scripts\ytdlp-tool.exe subs "https://www.youtube.com/watch?v=VIDEO_ID" --list
```

On Linux or macOS use `.venv/bin/...`. Optional extras: `.[asr]` for Whisper transcription ([docs/transcription.md](docs/transcription.md)) and `.[instagram]` for Instagram photo posts and carousels. `python -m ytdlp_tool ...` is equivalent to `ytdlp-tool ...`.

Every command is described in [docs/cli-reference.md](docs/cli-reference.md).

## Configuration

The CLI needs no configuration. The Telegram bot and the Digital Concert Hall bridge read these environment variables (names and meaning in [.env.example](.env.example)):

- `YTDL_TELEGRAM_BOT_TOKEN`, `YTDL_ALLOWED_CHAT_IDS`, `YTDL_ALLOW_PUBLIC_BOT`: Telegram bot.
- `YTDLP_DCH_OUTPUT`, `YTDLP_DCH_STATE`, `YTDLP_DCH_EXTENSION_ORIGIN`: Digital Concert Hall jobs and host.

On Ops the bot launcher reads the token and the allowlist from protected files outside the repository ([docs/operations.md](docs/operations.md)). Never commit real values.

## Project layout

```text
src/ytdlp_tool/      the package: CLI, workflows, Telegram bot, Digital Concert Hall host, worker, MCP server, installer
tests/               pytest unit tests (no network, ffmpeg or GPU needed); tests/e2e/ holds an opt-in browser test
extensions/dch-bridge/  Manifest V3 Brave/Chromium extension for the Digital Concert Hall bridge
plugins/ytdl/        skills-only ChatGPT plugin that invokes the toolkit
scripts/             bot launcher and scheduled-task installer; scripts/asr-benchmarks/ holds the Persian ASR research tools
docs/                user and operator guides, project history, archived plans and benchmark logs (index: docs/README.md)
output/              runtime output, git-ignored except .gitkeep
```

## Testing

```powershell
python -m pytest tests/ -q -p no:cacheprovider
python -m ruff check .
```

The browser end-to-end test for the Digital Concert Hall bridge (`tests/e2e/run_dch_e2e.sh`) needs Node, Playwright and Xvfb and is not part of the default run.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: [SECURITY.md](SECURITY.md). Project background: [docs/HISTORY.md](docs/HISTORY.md).

## License

[MIT](LICENSE). Downloading content is subject to each site's terms and to copyright law; use this tool only for content you are allowed to download.
