# Contributing

Thanks for your interest. This is a small personal project; issues and focused pull requests are welcome.

## Set up

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"     # add ,asr or ,instagram for those extras
```

Install [ffmpeg](https://ffmpeg.org/) if you work on audio, clips or transcription.

## Run the checks

```powershell
python -m pytest tests/ -q -p no:cacheprovider
python -m ruff check .
```

Tests use fakes for yt-dlp, Telegram and subprocesses and need no network, ffmpeg or GPU. Add or update a test with every behaviour change. The browser test `tests/e2e/run_dch_e2e.sh` is optional (Node, Playwright, Xvfb).

## Branches and commits

- Branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `chore/<topic>`.
- Use [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`, `chore: ...`.
- Keep pull requests small and describe how you tested them. Update `CHANGELOG.md` for user-visible changes.

## Ground rules

- Never commit tokens, chat IDs, cookies or downloaded media. Configuration names are in `.env.example`.
- Do not add features that bypass DRM, logins or paywalls.
- `scripts/start-telegram-bot.ps1` is started by a scheduled task on the maintainer's machine: keep its path and name.
- Documentation and scripts use lowercase-kebab-case file names.
