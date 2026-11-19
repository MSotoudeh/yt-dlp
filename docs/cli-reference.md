# CLI reference

Every `ytdlp-tool` command with examples. `python -m ytdlp_tool ...` is equivalent. Except for the `dch` commands, which use your own Digital Concert Hall account ([guide](digital-concert-hall.md)), nothing here needs a login or an API key.

## Command overview

```text
ytdlp-tool subs URL [options]
ytdlp-tool transcript YOUTUBE_URL [--lang auto] [--format txt|srt] [--model small]
ytdlp-tool info URL
ytdlp-tool formats URL
ytdlp-tool video URL [options]
ytdlp-tool audio URL [options]
ytdlp-tool thumbnail URL [options]
ytdlp-tool playlist URL [options]
ytdlp-tool clip URL START END [options]
ytdlp-tool comments URL [options]
ytdlp-tool transcribe URL_OR_LOCAL_FILE [--lang auto] [--model small] [--video]
ytdlp-tool ig-caption|ig-media|ig-speech INSTAGRAM_URL [options]
ytdlp-tool x-post URL | li-post URL [--output-dir DIR]
ytdlp-tool dch URL [--list] [--item N] [--token-stdin] [--format-selector SEL]
ytdlp-tool dch-start [URL] [--list] [--item N]     # background job via the signed-in Brave session
ytdlp-tool dch-status [JOB_ID]
```

The equivalent module form is `python -m ytdlp_tool ...`.

## Subtitles

List languages:

```powershell
ytdlp-tool subs "https://www.youtube.com/watch?v=VIDEO_ID" --list
```

Download English subtitles as plain text:

```powershell
ytdlp-tool subs "URL" --lang en --format txt
```

Automatic language selection prefers manual captions in the video's declared spoken language, then original-language automatic captions (such as `de-orig`). Without source-language metadata, it accepts an unambiguous `-orig` track; otherwise it reports original captions unavailable rather than guessing from translated tracks. The `transcript` workflow then falls back to local ASR. An explicitly requested language remains a separate override and is never silently replaced.

## Transcript-first YouTube text

The `transcript` command prefers the caption track behind YouTube's **Show transcript** panel **in the original spoken language**. It never auto-selects YouTube's machine-translated Persian/English captions for foreign-language speech. If no reliably identified original-language caption is available (or the original track is empty), it uses local `faster-whisper` on the original audio and returns TXT/SRT. No translation is performed; a downstream LLM can translate on demand. The output reports `Source: youtube_manual`, `youtube_automatic`, or `asr` plus the transcript language. Authentication failures or download timeouts are not treated as missing captions.

```powershell
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcript "https://youtu.be/VIDEO_ID" --model large-v3 --model-dir output\chatgpt\asr-models
```

The independent Telegram bot displays inline **TXT (plain text)** and **SRT (timed subtitles)** buttons for a bare YouTube URL; `/txt URL` and `/srt URL` select a format directly. The CLI supports `transcript URL --format txt|srt` while preserving the existing no-`--format` behavior. Native YouTube SRT cues use their published timestamps and do not require ASR. `/audio`, `/subs` and `/transcribe` remain explicit overrides.

## Instagram caption and speech

The private `@You_TubeDL_bot` now sends **two separate Telegram deliveries** for a bare Instagram post/Reel URL: (1) native Telegram photo/video (or an album for carousels), and (2) the author's full written caption as selectable Telegram chat text, **not a TXT attachment**. Instagram media is downloaded only to the Ops working directory for uploading; neither OCR nor ASR is used. Public video/Reel downloads use yt-dlp; photo posts and carousels use anonymous Instaloader public post metadata, with gallery-dl as a fallback. Install `instaloader` and `gallery-dl` in the same isolated Python environment (`pip install -e '.[instagram]'` or install extras separately). Verified on Ops 2026-11-05: one previously failing JPEG post and all eight JPEGs from a previously failing carousel, together with their original written captions, without a login or Meta API. Instagram access conditions can change, so failures are explicitly reported; no browser cookies are extracted. When media fails but the written caption is available, the bot still sends the text and reports the media error. To transcribe speech instead, use `/igtxt URL` or `/igsrt URL`; `/ig_choose URL` opens the optional format menu. Story overlay text requires OCR (not implemented), and Stories may require login.

```powershell
ytdlp-tool ig-caption "https://www.instagram.com/reel/SHORTCODE/"
ytdlp-tool ig-speech "https://www.instagram.com/reel/SHORTCODE/" --format txt --model large-v3
ytdlp-tool ig-speech "https://www.instagram.com/reel/SHORTCODE/" --format srt --model large-v3
```

Bot shortcuts: `/igcaption URL`, `/igtxt URL`, `/igsrt URL`.

## Metadata and formats

```powershell
ytdlp-tool info "URL"
ytdlp-tool formats "URL"
```

`info` is JSON-friendly for automation. `formats` exposes the yt-dlp format IDs that can be passed into `video` or `clip`.

## Video and audio

```powershell
ytdlp-tool video "URL"
ytdlp-tool video "URL" --format-selector "bv*[height<=1080]+ba/b"
ytdlp-tool audio "URL" --codec mp3 --quality 192
```

The default video selector is `bv*+ba/b`. Audio uses yt-dlp's best audio input and ffmpeg extraction.

## Whisper speech-to-text

The optional `transcribe` command generates **TXT + time-coded SRT from actual audio**, even when a video has no captions. For an isolated one-time installation on Ops and working Instagram/YouTube/local-file examples, read [transcription.md](transcription.md).

## Thumbnail

```powershell
ytdlp-tool thumbnail "URL"
```

This downloads the thumbnail only and skips the media stream.

## Playlists

Inspection is the safe default:

```powershell
ytdlp-tool playlist "PLAYLIST_URL" --limit 20
```

Downloading requires an explicit mode:

```powershell
ytdlp-tool playlist "PLAYLIST_URL" --download video --limit 20
ytdlp-tool playlist "PLAYLIST_URL" --download audio --limit 20
```

The explicit `--download` requirement prevents an accidental large playlist download.

## Clips

```powershell
ytdlp-tool clip "URL" 01:30 02:10
ytdlp-tool clip "URL" 90 130 --format-selector "160+139"
```

Timestamps accept seconds, `MM:SS`, or `HH:MM:SS`. yt-dlp download ranges plus ffmpeg are used instead of downloading and manually trimming a full file afterward.

## Comments

```powershell
ytdlp-tool comments "URL" --limit 100
```

The result is emitted as JSON and is intentionally bounded by `--limit`.

## Backward compatibility

Version 0.1 subtitle syntax still works:

```powershell
ytdlp-tool "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --format srt
```

## X / Twitter: original post media and separate text

Paste a public `https://x.com/USERNAME/status/ID` or `https://twitter.com/USERNAME/status/ID` link into the private `@You_TubeDL_bot`. It sends the **original attached photo/video (or native Telegram album) first**, then the post's **written text as a separate Telegram message**. It does not send a TXT attachment, run speech ASR, or perform OCR. A text-only post produces only a text message. Quoted/parent posts' media are not silently substituted for the linked post's attachments.

CLI: `python -m ytdlp_tool x-post URL --output-dir output/chatgpt/x-posts`. Internal text files are kept only on Ops to pass the bot's processing stage; they are not uploaded. Telegram aliases: `/tweet URL`, `/x URL`, `/xpost URL`.

Single-post metadata comes from X's **public embedded-post syndication JSON**; attached photos and MP4s come only from the expected `pbs.twimg.com` / `video.twimg.com` CDN domains. It requires neither an X developer key nor account cookies or login. Syndication is an undocumented public endpoint, may change or rate-limit, and is not a guaranteed free X API. Private, deleted, protected or inaccessible posts produce an explicit error. Downloaded media is validated and size-bounded before upload. Large video variants may fall back to smaller MP4 variants; overly large/unsupported attachments are reported while retaining accessible post text.

Validated on Ops 2026-11-05 with real public text-only, photo and video posts, both direct CLI and actual post retrieval through the bot job pipeline. Two controlled jobs in the existing allowlisted private Telegram chat verified real Bot API sendPhoto/sendVideo followed by sendMessage; both ended in SQLite state `done` with no error.

## LinkedIn public posts: native media and separate authored text

Send a public LinkedIn post URL (/posts/... or /feed/update/urn:li:activity:ID) to the private @You_TubeDL_bot. The bot sends publicly accessible media **first** as native Telegram photos, an album, an MP4 video or a GIF animation, then sends the author's written post description in a **separate ordinary text message**. No TXT file is attached. Text-only posts produce only text. Supported aliases: /linkedin URL, /li URL, /lipost URL. CLI: python -m ytdlp_tool li-post URL --output-dir output/chatgpt/linkedin-posts.

Retrieval uses LinkedIn's public Embed view for the post's numeric activity ID, without login, cookies or an official paid API. Author text comes from the original commentary, not a potentially truncated social preview. Only attached gallery photos and actual MP4 variants are selected; avatars, previews and comments are excluded. CDN domains and file payloads are validated, redirects are blocked, and uploads are bounded by Telegram limits. Large animated GIF files use Telegram sendAnimation. No OCR or speech ASR runs.

**Limitations:** This is HTML parsing, not a stable LinkedIn API. Protected, deleted and login-restricted posts cannot be guaranteed. Some public embeds hide album slides: a real nine-photo post exposed only five images with a +4 label. The bot sends those five and explicitly reports the four missing items. Text means the author's written post caption, **not** speech transcription or subtitles on video. Video and image format limitations remain explicit.

Real Ops smoke tests on 2026-11-05 covered public MP4 video, a five-photo gallery, an 11 MB animated GIF and a text-only post. Three separate live Telegram jobs, for sendVideo, sendMediaGroup and sendAnimation followed by normal text messages, reached SQLite state done without an error after the media-send error-state fix. All results were sent only to the existing private allowlisted chat.

## ChatGPT private plugin

The repository includes a skills-only private ChatGPT plugin source under `plugins/ytdl/`.
When installed as **YTDL**, it maps `@YTDL` requests to the toolkit on the Ops machine through Remote Desktop Commander.

Examples:

```text
@YTDL https://youtu.be/...                 # automatic subtitle -> TXT
@YTDL formats https://youtu.be/...         # list formats
@YTDL audio https://youtu.be/...           # extract MP3
@YTDL clip https://youtu.be/... 01:30 02:10
```

The plugin is intentionally a thin invocation layer: the implementation remains in this repository rather than being duplicated in plugin instructions.

## Ideas not yet built

Useful future additions include authenticated/cookie workflows, batch jobs, richer playlist policies, SponsorBlock/chapter actions, archive management, and machine-oriented task manifests.

Browser cookies are not read automatically; authenticated workflows should require explicit authorization.
