# yt-dlp automation toolkit

A reusable Python automation layer around upstream [yt-dlp](https://github.com/yt-dlp/yt-dlp).
Version 0.2 expands the original subtitle-only workflow into a multi-command media toolkit while keeping the old subtitle CLI compatible.

## Capabilities

The CLI now exposes these high-value yt-dlp workflows:

- `subs` — list or download manual/automatic subtitles as VTT, SRT, or TXT;
- `info` — normalized metadata as JSON;
- `formats` — available format IDs, containers, resolution/codecs, and size;
- `video` — download media with a yt-dlp format selector;
- `audio` — extract audio through ffmpeg;
- `thumbnail` — download the thumbnail without media;
- `playlist` — inspect a playlist or explicitly download it;
- `clip` — download only a selected time range;
- `comments` — fetch a bounded number of comments as JSON.

Non-subtitle commands accept ordinary HTTP(S) URLs supported by yt-dlp extractors. The current subtitle workflow intentionally remains YouTube-only.

## Requirements

- Python 3.11+
- Internet access
- `yt-dlp` (installed as a project dependency)
- `ffmpeg` for audio extraction, clipping, and formats that require muxing

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
ytdlp-tool info URL
ytdlp-tool formats URL
ytdlp-tool video URL [options]
ytdlp-tool audio URL [options]
ytdlp-tool thumbnail URL [options]
ytdlp-tool playlist URL [options]
ytdlp-tool clip URL START END [options]
ytdlp-tool comments URL [options]
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

Automatic language selection prefers manual English, then another manual language, then automatic English, then another automatic language.
An explicitly requested language is never silently replaced.

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

## Next layers

The adapter is intentionally separated from the CLI so the same operations can later be exposed through an MCP/HTTP facade. Useful future additions include authenticated/cookie workflows, batch jobs, richer playlist policies, SponsorBlock/chapter actions, archive management, and machine-oriented task manifests.

Browser cookies are not read automatically; authenticated workflows should require explicit authorization.
