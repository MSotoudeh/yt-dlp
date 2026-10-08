# Independent bot: @You_TubeDL_bot

Separate from Happ and @Youtube_Baz_bot.

This is an **unreleased Ops-only bot prototype**, not a deployed bot and not serverless. It requires an operator-provisioned YTDL_TELEGRAM_BOT_TOKEN and existing asr-venv with yt-dlp, ffmpeg and Whisper large-v3.

Run from repo root using the ASR Python:
```powershell
$env:YTDL_TELEGRAM_BOT_TOKEN = (Get-Content 'C:\ProgramData\ytdlp-bot\telegram-token' -Raw).Trim()
$env:YTDL_ALLOWED_CHAT_IDS = '<YOUR_PRIVATE_TELEGRAM_CHAT_ID>'
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool.telegram_bot --python .\output\chatgpt\asr-venv\Scripts\python.exe --model-dir .\output\chatgpt\asr-models
```

Never commit token or reveal it in logs. Rotate token exposed in chat. Ops-local SQLite persists received jobs and prevents duplicate ingestion. It does **not** retain messages sent while Ops is offline. Video/audio output currently remains on Ops and **is not delivered to Telegram**, so do not advertise production completion. Next steps: upload media safely, improve limits and retries, lock down admin access, add Cloudflare Worker+Queue (confirm costs first), install managed service, real end-to-end testing and recovery.
