---
name: ytdl-workflow
description: Use whenever the YTDL plugin is explicitly invoked or the user asks to run their local yt-dlp toolkit on Ops for subtitles, speech-to-text, metadata, media downloads, thumbnails, playlists, clips, or comments.
---

# YTDL workflow

This plugin is a thin invocation layer over the user's version-controlled toolkit at `C:\GitHub\yt-dlp` on the Windows device named **Ops**.

## Execution contract

- Prefer **Remote Desktop Commander** and select **Ops** when more than one device is available. If the service is quota-blocked or unavailable, use the authorized **Project IR** remote executor on device `ops` instead; do not retry or reconnect a quota-blocked service.
- Work from `C:\GitHub\yt-dlp`.
- Invoke the toolkit with `python -m ytdlp_tool ...`.
- Do not substitute raw `yt-dlp` shell commands when the toolkit already exposes the requested operation.
- Do not edit source code, switch branches, commit, pull, or push during an ordinary YTDL request.
- If a process is still running, read its existing process output instead of starting the same command again.
- Treat generated paths on Ops as remote paths; never claim a file is attached to ChatGPT unless it has actually been transferred.

## Default behavior

When the user invokes YTDL with only a YouTube URL and no operation, interpret it as:

```powershell
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcript "URL" --lang auto --model large-v3 --model-dir output\chatgpt\asr-models --output-dir output\chatgpt\transcripts
```

For a YouTube URL alone, ONLY use YouTube's published captions in the video's original SPOKEN language (manual first, then native-language automatic, e.g. `de-orig`). Do not automatically select machine-translated Persian/English captions for non-Persian/non-English speech. If native captions are absent or cannot be reliably identified, run ASR on the ORIGINAL audio, retaining that original language; downstream LLM translation is a separate, optional operation. Never treat YouTube access errors, timeouts, or caption-download failures as proof of absent captions; report them instead. Report transcript provenance (`youtube_manual`, `youtube_automatic`, or `asr`). For an Instagram post or Reel URL alone, the Telegram bot now automatically delivers **the accessible photo/video (native Telegram media or album)** and **the full author's written caption in a separate normal Telegram text message**. It does not attach TXT files and does not run OCR/ASR. Photos/carousels use anonymous Instaloader public-post metadata first (with gallery-dl fallback); video/Reels use yt-dlp. Verified public photo and eight-image carousel retrieval on Ops without account login on 2026-11-05. Access conditions may change; failure to download media does not suppress a separately retrievable caption. Spoken TXT/SRT remain available on explicit `/igtxt URL` or `/igsrt URL`; `/ig_choose URL` opens an optional format menu. For direct YTDL requests without a specified format, retrieve the author's caption first with no media download. Never silently download a full video for a text-only request.

After completion, read the generated TXT file and return its contents or summarize it according to the user's request.

## Intent mapping

Map natural-language requests to these commands:

- transcript / text of YouTube video / متن گفتار یوتیوب:
  `transcript URL --lang auto --model large-v3 --model-dir output\chatgpt\asr-models --output-dir output\chatgpt\transcripts`
  - This is the DEFAULT for a bare YouTube URL; original-language caption-first, ASR if original-language captions are unavailable (even when translated tracks exist)
  - Do not download video/audio when a public caption track succeeds
- subtitles / subs / captions / زیرنویس:
  `subs URL --lang LANG --format FORMAT`
  - default language: `auto`
  - default format: `txt`
  - use `--list` when the user asks which subtitle languages exist
- Instagram Story URLs (`/stories/USERNAME/STORY_ID/`) have no reliably accessible standalone authored caption; overlay text requires OCR of pixels and stories typically require login. The bot recognizes them and explains the limitation rather than running any media processing.
- LinkedIn public post media and authored text:
  - CLI: li-post URL --output-dir output/chatgpt/linkedin-posts
  - For a bare public LinkedIn post link, the Ops Telegram bot delivers native photos, video, or GIF (or accessible partial album) and then the author's written post commentary as a separate normal text message; no TXT attachment or OCR/ASR.
  - Read only publicly embeddable posts; extract commentary and attached media, not OpenGraph previews, profile avatars or video speech transcript.
  - Some multi-photo posts publicly expose only part of an album. Clearly report hidden slides (such as +4) and do not fabricate missing media or claim a complete album.
  - No API key, cookies, LinkedIn login or media bypass. Private posts and changes to LinkedIn public Embed HTML can block access; report failures explicitly.
- X/Twitter status media and original written text:
  `x-post URL --output-dir output\\chatgpt\\x-posts`
  - Bare URLs on x.com/twitter.com in Telegram automatically produce native photo/video/album, then a **separate** ordinary message with the original tweet text; no TXT attachment
  - Text-only posts generate only a text message; quoted/parent post media is not substituted
  - The public X syndication endpoint (no paid API or login) supplies status text and media metadata; downloads use whitelisted twimg.com hosts, with size validation and MP4 fallback
  - Endpoint is undocumented, may be rate-limited or change, and cannot access protected/deleted statuses; do not use browser cookies
- Instagram post/Reel media:
  `ig-media URL --output-dir output\\chatgpt\\instagram-media`
  - Downloads accessible photo/video. Reel: yt-dlp. Photo/carousel: Instaloader in isolated Python (anonymous, no saved login or browser cookies), then gallery-dl as fallback (ignoring user config).
  - The Telegram bot sends media using native sendPhoto/sendVideo or sendMediaGroup, separate from the caption text.
- Instagram written post/Reel caption / text under post:
  `ig-caption URL --output-dir output\\chatgpt\\instagram-caption`
  - Reads metadata only, saves UTF-8 TXT; does not download audio/video or run ASR
- Instagram spoken transcript:
  `ig-speech URL --format txt|srt --model large-v3 --model-dir output\\chatgpt\\asr-models --output-dir output\\chatgpt\\instagram-speech`
  - Local multilingual Whisper on original audio; SRT includes timestamps; no implicit translation
  - The text burned into the video image requires separate OCR and is NOT included
- transcribe / speech-to-text / transcription:
  `transcribe URL_OR_LOCAL_FILE --lang auto --model small --output-dir output\chatgpt\transcribe`
  - Add `--video` if the user wants the video (or supplies only an Instagram Reel URL)
  - Existing public captions are not required; output is both TXT and SRT
  - On Ops use isolated Python: `& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcribe ...`
  - If the ASR environment is absent, install according to `docs/transcription.md` without modifying system Python
  - Reuse the existing cache with `--model-dir output\chatgpt\asr-models`
  - For Persian console output, set `$env:PYTHONIOENCODING='utf-8'`
- metadata / info:
  `info URL`
- formats / qualities / codecs:
  `formats URL`
- video:
  `video URL`
  - pass `--format-selector` only when the user specifies a quality/format constraint
- audio:
  `audio URL --codec CODEC --quality QUALITY`
  - defaults: mp3, 192
- thumbnail:
  `thumbnail URL`
- playlist:
  `playlist URL --limit N`
  - inspection is the default
  - only add `--download video` or `--download audio` when the user explicitly asks to download the playlist
- clip:
  `clip URL START END`
  - START and END are required; accept seconds, MM:SS, or HH:MM:SS
- comments:
  `comments URL --limit N`
  - default limit: 100

Use a per-operation output directory under `output\chatgpt\` for file-producing commands unless the user gives another destination.

## Language handling

When the user names an obvious language, map it to a standard subtitle tag when unambiguous, for example:

- English -> `en`
- Persian / Farsi -> `fa`
- Italian -> `it`

For `--lang auto`, refuse a translation track unless it is confidently in the original spoken language; if YouTube language metadata is absent, accept only an unambiguous `-orig` track. If native subtitles cannot be identified, `transcript` falls back to multilingual ASR. Explicit language overrides remain separate and should never silently choose another language. Never automatically translate the original transcript to Persian.

## Returning results

- `info`, `formats`, and `comments`: capture the command output and answer from it.
- TXT subtitles/transcripts: read the generated TXT file on Ops and use that content directly. Include the reported source and language.
- SRT/VTT subtitles: read and return the requested text when practical; also report the remote saved path.
- Video, audio, thumbnail, playlist downloads, and clips: report the exact saved path(s) on Ops and relevant operation details.
- For transcription report TXT/SRT/audio paths and optional video, language and model; read the text when requested. Mention speech recognition mistakes.
- Keep large outputs concise unless the user asks for the complete raw output.

## Errors and authentication

- Surface toolkit/yt-dlp errors clearly; do not hide extractor failures.
- Never inspect or extract Brave/Chrome/Firefox cookies automatically.
- If content requires login, age verification, or browser cookies, ask for explicit authorization before using any browser-auth data.
- Do not attempt DRM bypass.
- If ffmpeg is required and unavailable, report that requirement rather than silently changing the requested operation.

## Examples

- `@YTDL https://youtu.be/...` -> YouTube transcript first (manual or automatic, TXT); ASR only if absent
- `@YTDL subs https://youtu.be/... fa srt` -> Persian SRT
- `@YTDL formats https://youtu.be/...` -> available formats
- `@YTDL audio https://youtu.be/...` -> MP3 at default quality
- `@YTDL clip https://youtu.be/... 01:30 02:10` -> selected time range
- `@YTDL comments https://youtu.be/... 20` -> up to 20 comments
- `@YTDL transcribe https://www.instagram.com/reel/... --lang fa` -> audio + TXT/SRT
- `@YTDL https://www.linkedin.com/posts/...-activity-ID-TOKEN` -> public LinkedIn attached media and separate authored text, with partial-album disclosure
- `@YTDL https://x.com/USERNAME/status/ID` -> X/Twitter original post text plus attached media; report errors for protected content
- `@YTDL https://www.instagram.com/reel/...` -> fetch authored Caption TXT (metadata only), or ask whether speech TXT/SRT is intended if ambiguous
- `@YTDL ig-caption https://www.instagram.com/reel/...` -> authored Caption TXT
- `@YTDL ig-speech https://www.instagram.com/reel/... --format srt` -> original-language timed spoken transcript
