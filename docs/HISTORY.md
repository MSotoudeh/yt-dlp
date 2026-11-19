# Project history

## Why it started

In September 2026 the owner wanted a scriptable way to pull YouTube subtitles as plain text for reading and for feeding to LLMs. Instead of shell one-liners around the `yt-dlp` executable, a small Python package (`ytdlp-tool`) was built on the yt-dlp **Python API**, so the same core could later be called by other front-ends. The GitHub repository was named `yt-dlp` after the library it wraps; it is not a fork of upstream yt-dlp.

## Phases

| Period | Phase | What changed |
| --- | --- | --- |
| 2026-09-21 | v0.1 subtitle CLI | Design and plan (now in `archive/subtitle-cli-*.md`), subtitle selection core, VTT/SRT/TXT output. Merged as PR #1. |
| 2026-10-02 | v0.2 toolkit + ChatGPT plugin | `info`, `formats`, `video`, `audio`, `thumbnail`, `playlist`, `clip`, `comments`; a skills-only ChatGPT plugin (`plugins/ytdl`) that drives the toolkit on the Ops machine. PRs #2 and #3. |
| 2026-10-08 | v0.3 Whisper + Telegram bot | Optional `transcribe` with faster-whisper; a private, allowlisted long-polling Telegram bot run as a Windows scheduled task. |
| 2026-10-09 to 10-22 | Persian ASR research | GPU vs CPU and a dozen Persian fine-tuned models benchmarked locally ([asr-benchmarks.md](asr-benchmarks.md)). Outcome: no model can be ranked without a human reference; production stayed on `large-v3`. |
| 2026-10-26 | Consolidation | The three stacked feature branches and the Telegram work were merged into `main` in one octopus merge. |
| 2026-10-27 | Transcript-first | `transcript` prefers YouTube's published captions in the original spoken language and uses ASR only as a fallback; inline TXT/SRT choice in Telegram. |
| 2026-11-05 | Social posts | Instagram, X/Twitter and LinkedIn public posts: native media first, author text as a separate message, no logins or paid APIs. |
| 2026-11-17 | v0.4 hardening | Bot survives network errors, logs and restarts properly; code split into testable functions; ruff. Operations guide written. |
| 2026-11-17 | v0.5 Digital Concert Hall | Manual-token `dch` command, then the full plan: Brave extension, native-messaging host, detached worker, MCP server and installer (245 tests, browser end-to-end test on a fake site). |
| 2026-11-19 | Public-ready cleanup | README/CONTRIBUTING/SECURITY/LICENSE, docs index and archive, scripts regrouped, stale branch archived. |

## Changes of direction

- **CLI → many front-ends.** The project began as a CLI; the Telegram bot, the ChatGPT plugin and the MCP server were added as thin layers over the same functions rather than separate implementations.
- **ASR first → captions first.** Early YouTube text requests always ran Whisper (slow on CPU). After the benchmarks showed how expensive and imperfect ASR is, YouTube's own caption track became the default, with a strict rule never to pick machine-translated tracks.
- **Plan review before building.** The Digital Concert Hall plan was first judged over-built and reduced to a minimal `dch` command; the owner then asked for the full plan, which was built with the same security rules. The web (remote) path was deliberately not built.

## Previous state vs current state

| | Before 2026-11-19 | Now |
| --- | --- | --- |
| README | long feature log mixing usage and verification notes | structured overview; full command docs in `docs/cli-reference.md` |
| Docs | 17 files incl. 8 dated benchmark logs and a plan in `tasks/` | indexed `docs/`, one benchmark summary, history in `docs/archive/` |
| Scripts | 28 files, bot ops mixed with one-off benchmark jobs | bot launcher + installer; 12 research tools in `scripts/asr-benchmarks/` |
| Licence, contributing, security | missing | MIT, CONTRIBUTING.md, SECURITY.md |
| Branches | `main` + merged `claude/hopeful-shannon-06lkeu` | `main` only, archive tag kept |

## Unmerged lines of work

None. The only extra branch, `claude/hopeful-shannon-06lkeu` (2026-11-17, the Digital Concert Hall work), was already fully contained in `main`; its tip is preserved as tag `archive/claude/hopeful-shannon-06lkeu`.

## Known unfinished work

- Digital Concert Hall: no real download with a real account yet (quality, DRM, token lifetime unknown); MCP tools not yet confirmed visible in each desktop client.
- Persian ASR: the human-corrected reference transcript that would allow choosing a model has not been produced. C1Tech Small and CV17 large-v3 remain gated.
- The bot's Whisper path runs on CPU; a GPU path with fallback is not implemented.
- Instagram Story overlay text (needs OCR) is not supported; LinkedIn embeds can hide album slides.
- The bot processes one job at a time, so a long ASR job blocks the queue.
