# yt-dlp automation toolkit

A local automation repository built around upstream [`yt-dlp`](https://github.com/yt-dlp/yt-dlp). Subtitle retrieval is the first capability; the repository is intentionally named `yt-dlp` so it can grow into a broader media automation toolkit later.

## Current capability: YouTube subtitles

Version 0.1 can:

- inspect a YouTube video without downloading the media;
- list manual and auto-generated subtitle language tags;
- prefer manual subtitles over automatic captions for an explicitly requested language;
- select a sensible language automatically with `--lang auto`;
- save subtitles as VTT, SRT, or plain TXT;
- download subtitles only, never the video/audio in this workflow.

`--lang auto` uses this order:

1. manual English;
2. any manual subtitle;
3. automatic English;
4. any automatic subtitle.

An explicitly requested language is never silently replaced with a different language.

## Requirements

- Python 3.11+
- Internet access to YouTube
- `yt-dlp` (installed automatically as a project dependency)

No ffmpeg installation is required for the subtitle-only workflow. SRT and TXT are generated locally from VTT.

## Install

From PowerShell:

```powershell
cd C:\GitHub\yt-dlp
python -m pip install -e .
```

For development/testing:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -v
```

## Usage

List available subtitle languages:

```powershell
python -m ytdlp_tool "https://www.youtube.com/watch?v=VIDEO_ID" --list
```

Download English subtitles as SRT:

```powershell
python -m ytdlp_tool "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --format srt
```

Use automatic language selection and plain text output:

```powershell
python -m ytdlp_tool "https://www.youtube.com/watch?v=VIDEO_ID" --lang auto --format txt
```

Choose a different output directory:

```powershell
python -m ytdlp_tool "https://www.youtube.com/watch?v=VIDEO_ID" --lang en --format vtt --output-dir output\example
```

The installed console entry point is equivalent:

```powershell
ytdlp-tool "https://www.youtube.com/watch?v=VIDEO_ID" --list
```

## Project structure

```text
src/ytdlp_tool/
  cli.py          command-line interface
  downloader.py   yt-dlp integration and file output
  subtitles.py    URL validation, language selection, VTT conversion

tests/            unit tests
output/           generated files (ignored by Git)
docs/superpowers/ design and implementation notes
```

## Verified integration

The v1 workflow was verified against the public YouTube video `YE7VzlLtp-4` (Big Buck Bunny): manual subtitle discovery, automatic-caption discovery, and real VTT/TXT/SRT generation all succeeded without downloading the video.

## Planned expansion

This repository can later add ordinary audio/video downloads, format selection, playlists, metadata, thumbnails, comments, cookies/auth handling, batch jobs, and an MCP/HTTP facade. Those features should reuse the yt-dlp adapter rather than being coupled to the subtitle CLI.
