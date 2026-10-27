# yt-dlp automation toolkit

A reusable Python automation layer around upstream [yt-dlp](https://github.com/yt-dlp/yt-dlp).
Version 0.3 adds optional local Whisper transcription for Instagram, YouTube and local files while keeping all previous commands compatible.

## Capabilities

The CLI now exposes these high-value yt-dlp workflows:

- `subs` — list or download manual/automatic subtitles as VTT, SRT, or TXT;
- `transcript` — prefer YouTube's published Show transcript text, falling back to local ASR only if captions are missing;
- `info` — normalized metadata as JSON;
- `formats` — available format IDs, containers, resolution/codecs, and size;
- `video` — download media with a yt-dlp format selector;
- `audio` — extract audio through ffmpeg;
- `thumbnail` — download the thumbnail without media;
- `playlist` — inspect a playlist or explicitly download it;
- `clip` — download only a selected time range;
- `comments` — fetch a bounded number of comments as JSON;
- `transcribe` — download media audio and generate spoken-text TXT and SRT with Whisper.

Non-subtitle commands accept ordinary HTTP(S) URLs supported by yt-dlp extractors. The current subtitle workflow intentionally remains YouTube-only.

## Requirements

- Python 3.11+
- Internet access
- `yt-dlp` (installed as a project dependency)
- `ffmpeg` for audio extraction, clipping, and formats that require muxing, and transcription
- Optional `faster-whisper` + `numpy` for speech-to-text (see [setup](docs/transcription.md))

Subtitle VTT/SRT/TXT conversion itself does not require ffmpeg.

## Install

```powershell
cd C:\GitHub\yt-dlp
python -m pip install -e .
```

For development:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

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

The private `@You_TubeDL_bot` supports an Instagram post/Reel URL with three choices: **Caption** (the author's text in metadata, without downloading media), **Speech TXT**, or **Speech SRT** (local Whisper on the original spoken audio). OCR for text burned into video is not included. Only public content reachable through yt-dlp is supported without login; 403/login walls remain explicit errors.

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

## Whisper speech-to-text (version 0.3)

The optional `transcribe` command generates **TXT + time-coded SRT from actual audio**, even when a video has no captions. For an isolated one-time installation on Ops and working Instagram/YouTube/local-file examples, read [docs/transcription.md](docs/transcription.md).

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

## Project structure

```text
src/ytdlp_tool/
  cli.py          command routing and human/machine-readable output
  downloader.py   subtitle retrieval and output
  media.py        metadata, formats, media, playlist, comments, and clip workflows
  transcribe.py     Whisper-based transcription
  subtitles.py    subtitle language selection and VTT conversion

tests/            unit tests
output/           generated files (ignored by Git)
docs/superpowers/ design and implementation notes
```

## Verification

Version 0.2 is unit-tested with fake yt-dlp adapters and has been integration-checked against the public Big Buck Bunny video (`YE7VzlLtp-4`). Verified operations include:

- metadata extraction;
- format discovery;
- thumbnail-only download;
- a real two-second video+audio clip using yt-dlp ranges and ffmpeg;
- the existing manual/automatic subtitle workflow from version 0.1.

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

## Next layers

The adapter is intentionally separated from the CLI so the same operations can later be exposed through an MCP/HTTP facade. Useful future additions include authenticated/cookie workflows, batch jobs, richer playlist policies, SponsorBlock/chapter actions, archive management, and machine-oriented task manifests.

Browser cookies are not read automatically; authenticated workflows should require explicit authorization.
