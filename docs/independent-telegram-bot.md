# Independent bot: @You_TubeDL_bot

Separate from Happ and @Youtube_Baz_bot.

This is an **Ops-hosted long-polling service**, not Cloudflare serverless. On 2026-10-27 the existing Windows Scheduled Task `YTDLP-Independent-Telegram-Bot` was migrated from interactive logon to **SYSTEM + AtStartup** to run without a user session. The previous task XML is preserved at `C:\\ProgramData\\ytdlp-bot\\state\\service-config-backup\\task-before-system.xml`. After an explicit start it reported **Running**, with its Python parent/child processes present. Initial outbound Telegram `sendDocument` and bot identity were verified against the user's existing private chat; a new real user click from Telegram after deployment is still required to prove inbound callback-to-file end to end. Uses the isolated asr-venv, ffmpeg and cached Whisper large-v3.

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

Never commit token or reveal it in logs. The existing bot token remains in the protected local file. The scheduled launch script reads `C:\\ProgramData\\ytdlp-bot\\allowed-chat-ids` with restricted SYSTEM/admin ACLs; this presently permits only the one previously established private chat, not public strangers (unlike the old `*` setting). Ops-local SQLite persists received jobs and prevents duplicate ingestion. It does **not** retain messages sent while Ops is offline. Video/audio and transcription files are uploaded with Telegram sendDocument when each file is below the direct upload limit (~50 MB); large files are reported as too large. New inbound Instagram choice-to-file delivery remains unverified until a real Telegram user sends a link and taps a choice after service startup. Next steps: upload media safely, improve limits and retries, lock down admin access, add Cloudflare Worker+Queue (confirm costs first), install managed service, real end-to-end testing and recovery.

## Instagram post/reel text and speech

- Paste a public `https://www.instagram.com/reel/SHORTCODE/`, `/reels/SHORTCODE/`, `/p/SHORTCODE/` or `/tv/SHORTCODE/` link. **By default the bot immediately retrieves and sends the author's written post description as normal Telegram text and a UTF-8 TXT attachment, without choosing a button or processing audio/video.** Long captions are sent in multiple complete Telegram messages, without truncation.
- Optional **Speech TXT** or **Speech SRT**: send `/igtxt URL` or `/igsrt URL` to run local multilingual Whisper on original audio. The optional `/ig_choose URL` command presents the previous three-choice inline menu.
- **Story URLs** (`/stories/USERNAME/STORY_ID/`) are recognized, but their text is usually an overlay on image/video, not a standalone metadata caption. The bot reports that limitation without downloading media or using OCR/ASR. Private/login-gated stories additionally require appropriate authorized access.
- Direct commands: `/igcaption URL`, `/igtxt URL`, `/igsrt URL`, `/ig_choose URL`. `/caption URL` aliases `/igcaption URL`. CLI equivalents: `ig-caption URL` and `ig-speech URL --format txt|srt`.
- **Do not confuse the authored Instagram caption with video speech**. Native Instagram auto-captions/hardcoded video text are not independently accessible through yt-dlp; spoken text uses ASR. OCR of text burned into the image is **not implemented** (a separate, explicitly chosen workflow would be needed).
- Only public accessible content is supported without user-granted authentication. No cookies are inspected or extracted. A missing/blocked caption produces an explicit error, never fabricated text.
- Optional Telegram inline callbacks are bound to the requesting chat/user, and repeat clicks are deduplicated. Automatic Caption retrieval never starts ASR.
