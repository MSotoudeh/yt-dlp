---
name: ytdl-workflow
description: Use whenever the YTDL plugin is explicitly invoked or the user asks to run their local yt-dlp toolkit on Ops for subtitles, speech-to-text, metadata, media downloads, thumbnails, playlists, clips, or comments.
---

# YTDL workflow

This plugin is a thin invocation layer over the user's version-controlled toolkit at `C:\GitHub\yt-dlp` on the Windows device named **Ops**.

## Execution contract

- Use **Remote Desktop Commander** and select the device named **Ops** when more than one device is available.
- Work from `C:\GitHub\yt-dlp`.
- Invoke the toolkit with `python -m ytdlp_tool ...`.
- Do not substitute raw `yt-dlp` shell commands when the toolkit already exposes the requested operation.
- Do not edit source code, switch branches, commit, pull, or push during an ordinary YTDL request.
- If a process is still running, read its existing process output instead of starting the same command again.
- Treat generated paths on Ops as remote paths; never claim a file is attached to ChatGPT unless it has actually been transferred.

## Default behavior

When the user invokes YTDL with only a YouTube URL and no operation, interpret it as:

```powershell
python -m ytdlp_tool subs "URL" --lang auto --format txt --output-dir output\chatgpt\subs
```

For an Instagram Reel URL alone, default to `transcribe URL --video` so TXT/SRT and the video are produced together. Other YouTube-only URL behavior is unchanged.

After completion, read the generated TXT file and return its contents or summarize it according to the user's request.

## Intent mapping

Map natural-language requests to these commands:

- subtitles / subs / captions / زیرنویس:
  `subs URL --lang LANG --format FORMAT`
  - default language: `auto`
  - default format: `txt`
  - use `--list` when the user asks which subtitle languages exist
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

If the exact requested tag is unavailable, report the available languages rather than silently choosing a different explicit language.

## Returning results

- `info`, `formats`, and `comments`: capture the command output and answer from it.
- TXT subtitles: read the generated TXT file on Ops and use that content directly.
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

- `@YTDL https://youtu.be/...` -> automatic subtitle as TXT
- `@YTDL subs https://youtu.be/... fa srt` -> Persian SRT
- `@YTDL formats https://youtu.be/...` -> available formats
- `@YTDL audio https://youtu.be/...` -> MP3 at default quality
- `@YTDL clip https://youtu.be/... 01:30 02:10` -> selected time range
- `@YTDL comments https://youtu.be/... 20` -> up to 20 comments
- `@YTDL transcribe https://www.instagram.com/reel/... --lang fa` -> audio + TXT/SRT
- `@YTDL https://www.instagram.com/reel/...` -> video + audio + transcript
