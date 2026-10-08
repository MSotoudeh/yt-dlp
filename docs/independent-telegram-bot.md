# Independent bot: @You_TubeDL_bot

Separate from Happ and @Youtube_Baz_bot.

This is an **Ops-hosted long-polling service**, not Cloudflare serverless. Initial deployment is registered in Windows Task Scheduler under `YTDLP-Independent-Telegram-Bot` (runs at mmsot logon; manually started for first run), with three crash-restart attempts. The live Telegram delivery path still needs an end-to-end chat test. It requires an operator-provisioned YTDL_TELEGRAM_BOT_TOKEN and existing asr-venv with yt-dlp, ffmpeg and Whisper large-v3.

Run from repo root using the ASR Python:
```powershell
$env:YTDL_TELEGRAM_BOT_TOKEN = (Get-Content 'C:\ProgramData\ytdlp-bot\telegram-token' -Raw).Trim()
$env:YTDL_ALLOWED_CHAT_IDS = '<YOUR_PRIVATE_TELEGRAM_CHAT_ID>'
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool.telegram_bot --python .\output\chatgpt\asr-venv\Scripts\python.exe --model-dir .\output\chatgpt\asr-models
```

Never commit token or reveal it in logs. Rotate token exposed in chat. Ops-local SQLite persists received jobs and prevents duplicate ingestion. It does **not** retain messages sent while Ops is offline. Video/audio and transcription files are uploaded with Telegram sendDocument when each file is below the direct upload limit (~50 MB); large files are reported as too large. Delivery remains unverified against a real Telegram chat until the user sends a new command. Next steps: upload media safely, improve limits and retries, lock down admin access, add Cloudflare Worker+Queue (confirm costs first), install managed service, real end-to-end testing and recovery.
