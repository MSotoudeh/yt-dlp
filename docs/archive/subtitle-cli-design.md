# yt-dlp Subtitle CLI Design

## Goal
Build the first reusable capability in a broader `yt-dlp` automation repository: retrieve YouTube subtitles from a URL and save them as SRT, VTT, or plain text.

## Scope
- Repository path: `C:\GitHub\yt-dlp`
- Python CLI wrapper around upstream `yt-dlp`.
- Accept only YouTube URLs in v1.
- List available manual and auto-generated subtitle languages.
- Prefer manual subtitles over auto-generated subtitles for the requested language.
- Support `srt`, `vtt`, and `txt` output.
- Save generated files under `output/` by default.
- No Whisper fallback in v1.
- No remote GitHub repository or push in v1.

## Architecture
`cli.py` parses arguments and prints user-facing results. `subtitles.py` owns URL validation, subtitle selection, and VTT-to-text conversion. `downloader.py` owns the `yt_dlp.YoutubeDL` integration and filesystem output.

The package will use the Python `yt-dlp` API rather than spawning shell commands, keeping the core reusable for a future MCP or API layer.
## CLI
Examples:
- `python -m ytdlp_tool URL --list`
- `python -m ytdlp_tool URL --lang en --format srt`
- `python -m ytdlp_tool URL --lang auto --format txt`

`--lang auto` selects a sensible available language, preferring manual English, then manual subtitles, then auto-generated English, then any auto-generated subtitle.

## Error Handling
Return clear non-zero failures for unsupported URLs, unavailable requested languages, videos without subtitles, and extractor/download errors. Do not silently fall back to a different explicit language.

## Testing
Unit tests cover URL validation, subtitle source selection, and VTT-to-text conversion. Integration verification uses a public YouTube video and the real `yt-dlp` extractor without downloading media.

## Extensibility
Keep `yt-dlp` as the repository identity. Future modules may expose metadata, audio/video downloads, playlists, format selection, thumbnails, comments, and an MCP facade without coupling those features to subtitle-specific code.