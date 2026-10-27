# Independent bot: @You_TubeDL_bot

Separate from Happ and @Youtube_Baz_bot.

This is an **Ops-hosted long-polling service**, not Cloudflare serverless. Initial deployment is registered in Windows Task Scheduler under `YTDLP-Independent-Telegram-Bot` (runs at mmsot logon; manually started for first run), with three crash-restart attempts. The Telegram API bot identity and outbound sendDocument delivery were verified with a real private chat on 2026-10-27; the complete inbound callback-to-file flow still needs an end-to-end live Telegram test with the long-polling process actually running. On 2026-10-27, the scheduled task was `Ready` with no bot process; attempting a manual start while the account was not interactively signed in left it `Queued`, and the queued request was cleared without changing its principal. An unattended Windows service / non-interactive account would need a separate reviewed deployment, not just a code edit. It requires an operator-provisioned YTDL_TELEGRAM_BOT_TOKEN and existing asr-venv with yt-dlp, ffmpeg and Whisper large-v3.

Run from repo root using the ASR Python:
```powershell
$env:YTDL_TELEGRAM_BOT_TOKEN = (Get-Content 'C:\ProgramData\ytdlp-bot\telegram-token' -Raw).Trim()
$env:YTDL_ALLOWED_CHAT_IDS = '<YOUR_PRIVATE_TELEGRAM_CHAT_ID>'
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool.telegram_bot --python .\output\chatgpt\asr-venv\Scripts\python.exe --model-dir .\output\chatgpt\asr-models
```

## YouTube transcript-first behavior

- A plain YouTube URL (including a link embedded in a message) creates a two-button inline choice: **TXT - Plain text** or **SRT - Timed subtitles**. Nothing is downloaded until a button is selected. Telegram callback queries are stored and deduplicated in SQLite; only the original requesting Telegram user in that chat can select a format.
- Direct commands `/txt URL` or `/srt URL` skip the buttons. `/transcript URL` keeps its previous default behavior (native TXT and ASR fallback TXT+SRT).
- Prefer manual captions **in the video's spoken language**, then automatic captions **in that same original language** (e.g. `de-orig` for German). Never auto-select YouTube's translated Persian, English or other tracks when the speech is in another language. Save original-language TXT and report `source=youtube_manual` or `source=youtube_automatic`.
- If original-language captions cannot be identified confidently, are absent, or are empty, download the original audio and run local multilingual Whisper ASR; return original-language TXT/SRT with `source=asr`. Downstream LLM translation to Persian is optional and performed only when requested.
- Errors such as 403, 429, and caption download timeouts are reported as errors rather than silently launching ASR. Caption retrieval may fail due to provider access conditions.
- Explicit `/audio URL`, `/video URL`, `/subs URL`, and `/transcribe URL` retain their meanings. `/transcript URL` runs the original automatic format selection. `/txt` delivers only UTF-8 TXT; `/srt` delivers only SRT with YouTube's original cue timestamps (or ASR times if native captions are absent).
- Bot runs the ASR fallback with the existing isolated ASR Python environment and cached `large-v3` model. Successful caption runs avoid audio/video downloads and model inference altogether.

Never commit token or reveal it in logs. Rotate token exposed in chat. Ops-local SQLite persists received jobs and prevents duplicate ingestion. It does **not** retain messages sent while Ops is offline. Video/audio and transcription files are uploaded with Telegram sendDocument when each file is below the direct upload limit (~50 MB); large files are reported as too large. Delivery remains unverified against a real Telegram chat until the user sends a new command. Next steps: upload media safely, improve limits and retries, lock down admin access, add Cloudflare Worker+Queue (confirm costs first), install managed service, real end-to-end testing and recovery.
