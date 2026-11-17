# Operations guide

How the Ops machine runs this project day to day: the Telegram bot service, logs, recovery, and
the development checks. Paths are for the Ops machine (`C:\GitHub\yt-dlp`).

## Telegram bot service

| Item | Value |
| --- | --- |
| Scheduled task | `YTDLP-Independent-Telegram-Bot` (SYSTEM, at startup) |
| Launcher | `scripts\start-telegram-bot.ps1` |
| Task installer / repair | `scripts\Install-BotTask.ps1` (elevated PowerShell, safe to re-run) |
| State directory | `C:\ProgramData\ytdlp-bot\state` (`jobs.sqlite`, `downloads\`, logs) |
| Secrets | `C:\ProgramData\ytdlp-bot\telegram-token`, `...\allowed-chat-ids` (never commit these) |

### Common commands

```powershell
# is it running?
Get-ScheduledTask -TaskName 'YTDLP-Independent-Telegram-Bot' | Get-ScheduledTaskInfo
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ytdlp_tool.telegram_bot' }

# start / stop
Start-ScheduledTask -TaskName 'YTDLP-Independent-Telegram-Bot'
Stop-ScheduledTask  -TaskName 'YTDLP-Independent-Telegram-Bot'

# read the log
Get-Content C:\ProgramData\ytdlp-bot\state\bot.log -Tail 50

# (re)create the task with the recommended restart settings
powershell -ExecutionPolicy Bypass -File C:\GitHub\yt-dlp\scripts\Install-BotTask.ps1
```

### Logs

All in `C:\ProgramData\ytdlp-bot\state`, rotated by the launcher at 5 MB (one `.1` generation kept):

* `bot.log` – the bot's own lines (job start/finish/failure, polling problems) plus the launcher's
  lines (start, exit code, missing secret files). **Start here.**
* `bot.stderr.log` / `bot.out.log` – whatever escapes the bot (interpreter crash, import error).

Logs never contain the bot token or message bodies. Job errors are limited to the first 300 characters.

### What keeps the bot alive

1. **In-process:** a failed `getUpdates` (network down, Telegram error) is retried with exponential
   backoff capped at 60 s. The bot does not exit for transient network trouble.
2. **Task Scheduler:** if the process does exit, the task restarts it (999 attempts, 1 minute apart),
   also when running on battery. Before 0.4.0 the task restarted only 3 times and stopped on battery,
   so a network outage around boot could leave the bot dead until the next reboot.
3. **Crash visibility:** an unexpected exception is written with its traceback to `bot.log`, and the
   bot exits with code 1 so step 2 applies.

### Troubleshooting

| Symptom | Check |
| --- | --- |
| Bot silent, task state `Ready` | `Get-ScheduledTaskInfo` (last result), then `bot.log` tail. Start the task. |
| `launcher failed: ... file missing` in `bot.log` | Recreate `telegram-token` / `allowed-chat-ids` under `C:\ProgramData\ytdlp-bot`. |
| `getUpdates failed ... retrying` repeating | Network or Telegram outage; it recovers by itself and logs `recovered`. |
| Job stuck `pending` in `jobs.sqlite` | The bot processes jobs one at a time; a long ASR job (up to 1 h timeout) blocks the queue. |
| `YTDL_ALLOWED_CHAT_IDS='*' would let anyone ...` | A wildcard allowlist now needs `YTDL_ALLOW_PUBLIC_BOT=1`. Prefer real chat IDs. |

### Security notes

* Only chat IDs in `allowed-chat-ids` can create jobs; other updates are recorded and ignored.
* A wildcard (`*`) allowlist is refused unless `YTDL_ALLOW_PUBLIC_BOT=1` is set, and the launcher
  never accepts it at all.
* Telegram texts for failures are generic by design; details stay in the job row and `bot.log`.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q          # unit tests, no network
python -m ruff check .       # lint (rules in pyproject.toml)
```

* Tests use fakes for yt-dlp, Telegram and subprocesses; none needs network, ffmpeg or a GPU.
* The one-off benchmark scripts in `scripts/` are kept as run (compact style, documented in
  `docs/persian-asr-*.md`); ruff ignores their purely stylistic rules, but still checks real errors.
* `output/` is git-ignored runtime data (downloads, venvs, models, packaged zips). It is safe to
  delete generated files there, but `output\chatgpt\asr-venv` and `asr-models` are used by the bot.

## Keeping Git and Ops in sync

Ops was once 14 commits ahead of GitHub with no backup. Push regularly:

```powershell
git status -sb      # "ahead N" means unpushed work
git push
```
