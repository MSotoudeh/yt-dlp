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

- Paste a public `https://www.instagram.com/reel/SHORTCODE/`, `/reels/SHORTCODE/`, `/p/SHORTCODE/` or `/tv/SHORTCODE/` link. **By default the bot downloads accessible original photos/video and sends native Telegram photo/video (or album), then sends the author's written caption as a separate ordinary Telegram text message. No TXT file is attached.** Media is stored temporarily on Ops and sent through multipart Telegram Bot API; no OCR or ASR. Long captions are sent completely across multiple text messages, without truncation. For video, yt-dlp is used; photo/album downloads use Instaloader's anonymous public post metadata first, then gallery-dl fallback. On 2026-11-05, a previously failing photo and every slide in a previously failing eight-image carousel downloaded on Ops without any Instagram login, together with both authored captions. The optional `instagram` project dependency installs both libraries. This method is subject to future Instagram changes and may still fail for private or login-gated posts. The bot reports failures rather than automatically extracting cookies or pretending content exists.
- Optional **Speech TXT** or **Speech SRT**: send `/igtxt URL` or `/igsrt URL` to run local multilingual Whisper on original audio. The optional `/ig_choose URL` command presents the previous three-choice inline menu.
- **Story URLs** (`/stories/USERNAME/STORY_ID/`) are recognized, but their text is usually an overlay on image/video, not a standalone metadata caption. The bot reports that limitation without downloading media or using OCR/ASR. Private/login-gated stories additionally require appropriate authorized access.
- Direct commands: `/igcaption URL`, `/igtxt URL`, `/igsrt URL`, `/ig_choose URL`. `/caption URL` aliases `/igcaption URL`. CLI equivalents: `ig-caption URL` and `ig-speech URL --format txt|srt`.
- **Do not confuse the authored Instagram caption with video speech**. Native Instagram auto-captions/hardcoded video text are not independently accessible through yt-dlp; spoken text uses ASR. OCR of text burned into the image is **not implemented** (a separate, explicitly chosen workflow would be needed).
- Only public accessible content is supported without user-granted authentication. No cookies are inspected or extracted. A missing/blocked caption produces an explicit error, never fabricated text.
- Optional Telegram inline callbacks are bound to the requesting chat/user, and repeat clicks are deduplicated. Automatic Caption retrieval never starts ASR.

## X / Twitter: same dual-delivery workflow

- A bare public `https://x.com/HANDLE/status/TWEET_ID` or `https://twitter.com/HANDLE/status/TWEET_ID` triggers **native Telegram photo/video/media group first, then the tweet's authored text as a separate normal Telegram message**, no TXT attachment. Direct commands `/tweet URL`, `/x URL`, `/xpost URL` work identically.
- Purely text posts send only the actual text; no fabricated media or transcript. Attached media only (not silently downloaded from quoted or parent posts). Links and Unicode tweet text are preserved. Very long messages are split safely.
- The `x-post` CLI workflow fetches the read-only public embedded-post syndication data (`cdn.syndication.twimg.com/tweet-result`), then streams media from whitelisted `pbs.twimg.com` / `video.twimg.com` hosts. It validates HTTPS, status IDs, no redirects, payload type and Telegram upload-size limits; large MP4 variants try a smaller bitrate version when available. Metadata is fetched once per job. Partial failures report missing media while still delivering available original text.
- No paid X API, login, cookies, browser session, OCR, ASR, or third-party tweet proxy is used. The syndication endpoint is **undocumented and may become unavailable**; do not promise unlimited public access. Private, deleted, age-restricted or protected statuses cannot be reliably retrieved.
- Verified 2026-11-05 using real public text, photo and video statuses. One real photo tweet and one real video tweet were queued into the already-authorized private bot chat on Ops; the production long-polling bot sent their native media via Telegram sendPhoto/sendVideo and authored text via sendMessage. Both jobs reached SQLite `done` with empty error. No public audience was enabled and the token never left the protected Ops service environment.

## LinkedIn public post support

- Bare public LinkedIn /posts/ or /feed/update/urn:li:activity:ID links, plus commands /linkedin, /li and /lipost, trigger the li_post workflow.
- Native Telegram photo/video/album/GIF is delivered first and the author's own full written commentary in a separate text message. Purely text posts send only text. A temporary local text file is never uploaded as a document.
- Only the public LinkedIn Embed view is read, using a validated numeric activity ID. Commentary is taken from the commentary element, and actual photos and MP4 variants from the associated media nodes. Logos, avatars, generic OpenGraph image previews, unrelated stories, and comments are excluded.
- Photo gallery embeds may hide slides. The bot warns if the public embed says +N hidden; on 2026-11-05 five of nine photos could be downloaded, not all nine. It never silently calls the partial result complete.
- Supports JPEG/PNG, native MP4 and GIF animation. Media is fetched from whitelisted LinkedIn CDN hosts, without redirects or cookies. Every media download is size-limited and checked for a valid file signature; alternate MP4 bitrate variants are tried when necessary. Partial failures still deliver accessible original text.
- No login, official LinkedIn API, browser-cookie extraction, OCR or ASR. LinkedIn can block public embed access or change its HTML at any time. Speech transcriptions and embedded subtitles are separate optional workflows, not implied by authored post captions.
- Ops verification on 2026-11-05: real public video, gallery, GIF and text-only extraction; four bot jobs completed with a recorded test Telegram transport. Real Telegram delivery is verified separately.
