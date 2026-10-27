# Independent bot: @You_TubeDL_bot

Separate from Happ and @Youtube_Baz_bot.

This is an **Ops-hosted long-polling service**, not Cloudflare serverless. Initial deployment is registered in Windows Task Scheduler under `YTDLP-Independent-Telegram-Bot` (runs at mmsot logon; manually started for first run), with three crash-restart attempts. The live Telegram delivery path still needs an end-to-end chat test. On 2026-10-27, the scheduled task was `Ready` with no bot process; attempting a manual start while the account was not interactively signed in left it `Queued`, and the queued request was cleared without changing its principal. An unattended Windows service / non-interactive account would need a separate reviewed deployment, not just a code edit. It requires an operator-provisioned YTDL_TELEGRAM_BOT_TOKEN and existing asr-venv with yt-dlp, ffmpeg and Whisper large-v3.

Run from repo root using the ASR Python:
```powershell
$env:YTDL_TELEGRAM_BOT_TOKEN = (Get-Content 'C:\ProgramData\ytdlp-bot\telegram-token' -Raw).Trim()
$env:YTDL_ALLOWED_CHAT_IDS = '<YOUR_PRIVATE_TELEGRAM_CHAT_ID>'
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool.telegram_bot --python .\output\chatgpt\asr-venv\Scripts\python.exe --model-dir .\output\chatgpt\asr-models
```

## YouTube transcript-first behavior

- A plain YouTube URL (including a link inside a message) runs the `transcript` operation, NOT `/audio`.
- Prefer YouTube manual captions, then original-language automatic captions (`fa-orig` where available). Save TXT with transcript text and report `source=youtube_manual` or `source=youtube_automatic`.
- Only if a valid public caption track is absent or empty, download audio and use local Whisper as fallback; return TXT and SRT with `source=asr`.
- Errors such as 403, 429, and caption download timeouts are reported as errors rather than silently launching ASR. Caption retrieval may fail due to provider access conditions.
- Explicit `/audio URL`, `/video URL`, `/subs URL`, and `/transcribe URL` retain their meanings. `/transcript URL` runs the new automatic selection explicitly.
- Bot runs the ASR fallback with the existing isolated ASR Python environment and cached `large-v3` model. Successful caption runs avoid audio/video downloads and model inference altogether.

Never commit token or reveal it in logs. Rotate token exposed in chat. Ops-local SQLite persists received jobs and prevents duplicate ingestion. It does **not** retain messages sent while Ops is offline. Video/audio and transcription files are uploaded with Telegram sendDocument when each file is below the direct upload limit (~50 MB); large files are reported as too large. Delivery remains unverified against a real Telegram chat until the user sends a new command. Next steps: upload media safely, improve limits and retries, lock down admin access, add Cloudflare Worker+Queue (confirm costs first), install managed service, real end-to-end testing and recovery.
