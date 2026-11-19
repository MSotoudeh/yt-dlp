# Subtitle CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Python CLI in the `yt-dlp` repository that lists and downloads YouTube subtitles as SRT, VTT, or TXT.

**Architecture:** Keep yt-dlp integration behind `downloader.py`; keep validation, selection, and text conversion in `subtitles.py`; keep argument parsing and terminal output in `cli.py`. Use the Python `yt_dlp` API so the same core can later be exposed through MCP or HTTP without shell parsing.

**Tech Stack:** Python 3.14, `yt-dlp`, `pytest`, standard library.

**Spec:** `docs/superpowers/specs/2026-09-13-subtitle-cli-design.md`

## Global Constraints
- Repository path is `C:\GitHub\yt-dlp`.
- Accept only YouTube URLs in v1.
- Manual subtitles take precedence over auto-generated subtitles for an explicit requested language.
- `--lang auto` preference order: manual English, any manual language, auto English, any auto language.
- Output formats: `srt`, `vtt`, `txt`.
- Default output directory: `output/`.
- No Whisper fallback, remote GitHub creation, or push in v1.

---

### Task 1: Core subtitle selection and conversion

**Files:**
- Create: `pyproject.toml`, `src/ytdlp_tool/__init__.py`, `src/ytdlp_tool/subtitles.py`
- Test: `tests/test_subtitles.py`

**Interfaces:**
- Produces: `validate_youtube_url(url)`, `select_subtitle(manual, automatic, requested)`, `vtt_to_text(content)`.

- [ ] Write focused tests for accepted/rejected YouTube URLs, manual-vs-auto selection, `auto` selection order, unavailable language, and VTT-to-text cleanup.
- [ ] Run `python -m pytest tests/test_subtitles.py -v` and confirm RED because production functions do not exist.
- [ ] Implement only enough core logic to satisfy those tests.
- [ ] Re-run the focused test module and confirm GREEN.
- [ ] Commit core behavior.

### Task 2: yt-dlp adapter and filesystem output

**Files:**
- Create: `src/ytdlp_tool/downloader.py`
- Test: `tests/test_downloader.py`

**Interfaces:**
- Consumes: subtitle selection helpers from Task 1.
- Produces: `inspect_video(url)`, `download_subtitle(url, language, output_format, output_dir)` and structured result data.

- [ ] Write failing tests around yt-dlp option construction and deterministic output handling, using a minimal fake YoutubeDL boundary rather than network access.
- [ ] Run `python -m pytest tests/test_downloader.py -v` and confirm RED.
- [ ] Implement the adapter using the `yt_dlp.YoutubeDL` Python API, with media download disabled.
- [ ] Implement TXT conversion from downloaded VTT while preserving SRT/VTT files as requested.
- [ ] Re-run downloader tests and full unit suite; confirm GREEN.
- [ ] Commit adapter behavior.

### Task 3: CLI surface

**Files:**
- Create: `src/ytdlp_tool/cli.py`, `src/ytdlp_tool/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: downloader inspection/download functions.
- Produces: `python -m ytdlp_tool URL --list` and `python -m ytdlp_tool URL --lang <lang> --format <fmt>`.

- [ ] Write failing CLI tests for `--list`, explicit language download, `--lang auto`, unsupported URL, and missing subtitles.
- [ ] Run `python -m pytest tests/test_cli.py -v` and confirm RED.
- [ ] Implement argparse CLI and stable exit codes/messages.
- [ ] Re-run CLI tests and full unit suite; confirm GREEN.
- [ ] Commit CLI behavior.

### Task 4: Packaging, docs, and real integration verification

**Files:**
- Create/modify: `.gitignore`, `README.md`, `pyproject.toml`
- Runtime output: `output/`

- [ ] Install project editable with `python -m pip install -e .` and verify `yt-dlp` dependency resolves.
- [ ] Run the full suite: `python -m pytest -v`.
- [ ] Run a real public-YouTube inspection with `python -m ytdlp_tool <URL> --list` without downloading media.
- [ ] Download one available subtitle as VTT and one as TXT; verify files are non-empty and TXT contains no WEBVTT timing/header lines.
- [ ] Document installation, usage, architecture, and future expansion points in README.
- [ ] Run `git status`, full tests, CLI help, and real integration verification again before claiming completion.
- [ ] Commit documentation and verified v1.
