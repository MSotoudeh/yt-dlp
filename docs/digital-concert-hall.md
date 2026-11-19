# Digital Concert Hall downloads

Download concerts and films from **your own** [Digital Concert Hall](https://www.digitalconcerthall.com) (DCH) account on this computer, either from a terminal or by asking Claude Desktop / Codex / ChatGPT. Persian version: [digital-concert-hall.fa.md](digital-concert-hall.fa.md).

> **Status (2026-11-17):** implemented and tested with 245 unit tests plus an end-to-end test that drives a real Chromium, the real extension, the real host and the real worker against a **fake** site with a **fake** token. A real download with a real account has **not** been run yet, so quality, DRM behaviour and token lifetime are still unknown (see "First real test" below). Design background: [archived plan](archive/digital-concert-hall-plan.md) and [plan review](archive/digital-concert-hall-plan-review.md) (both in Persian).

## Two ways to use it

| | A: Brave bridge (recommended) | B: manual token |
| --- | --- | --- |
| Command | `dch-start` / `dch-status`, or MCP tool `dch_start` | `dch` |
| Who fetches the token | the browser extension, automatically | you, copied from DevTools |
| Best for | Claude Desktop, Codex, ChatGPT Desktop | a one-off test or a script |
| Runs | in the background, with job status | in the foreground |

## A: Brave bridge

### Architecture

```text
Claude Desktop / Codex / ChatGPT Desktop
        │ MCP over stdio: dch_start · dch_status · dch_jobs   (no tool accepts or returns a token)
        ▼
  ytdlp_tool.dch_mcp ──(127.0.0.1 + random shared secret)──► ytdlp_tool.dch_host  (native-messaging host)
                                                                  │ "get_token"
                                                                  ▼
                                             Brave extension (only https://www.digitalconcerthall.com/*)
                                             reads the site's own localStorage and answers
                                                                  │ token
                                                                  ▼
          host ──(stdin of a separate process)──► dch worker ──► yt-dlp ──► files + status.json
```

The token only travels extension → host → worker stdin. It never appears in arguments, environment variables, files, logs, the clipboard, MCP responses or the chat. Unit tests and the browser test check this (for example, the token cannot be found anywhere in the state directory).

### Install (once, Windows)

1. In a normal (non-admin) PowerShell in the repository:

   ```powershell
   python -m ytdlp_tool.dch_install install   # host files, Brave registration, Claude Desktop + Codex config (with backups)
   python -m ytdlp_tool.dch_install status
   ```

   This writes the host launcher and manifest to `%LOCALAPPDATA%\ytdlp-tool\dch\native-host\`, registers `com.ytdlp_tool.dch` under `HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts`, and adds an MCP server named `ytdlp-dch` to Claude Desktop and Codex. The launcher points at this checkout's `src/` folder, so do not move the checkout after installing (or re-run `install`). Use `--browsers brave,chrome,edge` for other Chromium browsers and `--no-claude` / `--no-codex` to skip those clients.
2. In Brave: `brave://extensions` → **Developer mode** → **Load unpacked** → select `extensions/dch-bridge` in this repository. The extension ID must be `bcohebdjklmiaddlkbemjfioeloajdlj`; it is fixed by the public key in `manifest.json`, and the host only accepts that ID.
3. Fully quit and reopen Claude Desktop and Codex so they load the MCP server. The ChatGPT plugin (`plugins/ytdl`, 0.2.9) documents the same workflow.
4. Sign in to digitalconcerthall.com in Brave and leave the concert page open.

Uninstall: `python -m ytdlp_tool.dch_install uninstall`, then remove the extension from Brave.

### Use

Ask the assistant "download the Digital Concert Hall concert open in Brave", or give it the URL. From a terminal:

```powershell
python -m ytdlp_tool dch-start --list            # parts and best available quality; downloads nothing
python -m ytdlp_tool dch-start                   # download the open concert tab
python -m ytdlp_tool dch-start "https://www.digitalconcerthall.com/en/concert/56205" --item 2
python -m ytdlp_tool dch-status                  # recent jobs
python -m ytdlp_tool dch-status JOB_ID           # one job
```

- Without a URL: if exactly one concert, film or work tab is open (or only one is active) it is used. With several, the extension refuses and asks for the URL. A ChatGPT tab or any non-DCH tab is never picked.
- Output: `output\chatgpt\digital-concert-hall\<title> [<id>]\NN - <part> [<id>].<ext>` (override with `YTDLP_DCH_OUTPUT`). Existing files are not overwritten.
- Status and logs: `%LOCALAPPDATA%\ytdlp-tool\dch\jobs\<id>\status.json` and `%LOCALAPPDATA%\ytdlp-tool\dch\host.log` (override the base with `YTDLP_DCH_STATE`). Neither contains the token.

### Long downloads

- The worker is detached from the host and the browser; closing the chat or the browser does not stop it.
- `status.json` holds the pid, start time, time limit, state (`running` / `done` / `failed`), a sanitized error and the final files.
- The default time limit is 6 hours. After that the worker records a failure and deletes `.part` files.
- `done` is recorded only when every reported file exists and is non-empty. A dead or killed worker is reported as `failed`, never `running`.
- The same request while one is running returns `duplicate`; the same finished request returns `already_done`.
- Assistants are instructed to stop after starting a job and to check status once, only when asked (no polling).

### Extension permissions

Permanent permission for **one domain only**: `https://www.digitalconcerthall.com/*`, plus `scripting`, `nativeMessaging` and `alarms` (to reconnect). `activeTab` was rejected because it cannot find the open tab without a click. The extension has no general `tabs` or network access and only talks to the host `com.ytdlp_tool.dch`, which only talks to this extension. Any local process running as the same user can ask the bridge to start a download of a valid DCH URL, but can never obtain the token itself.

## B: Manual token (`dch`)

In Brave: DevTools → Application → Local Storage → `https://www.digitalconcerthall.com` → value of `access_token_production`. Then (the token is read from a hidden prompt and nothing is echoed):

```powershell
ytdlp-tool dch "https://www.digitalconcerthall.com/en/concert/56205" --list
ytdlp-tool dch "https://www.digitalconcerthall.com/en/concert/56205" --item 2 --format-selector "bv*[height<=1080]+ba/b"
# from a script: token on stdin, never as an argument or environment variable
... | ytdlp-tool dch URL --token-stdin
```

## Security guarantees

| Rule | How it is enforced and tested |
| --- | --- |
| Token not in argv, environment, files, logs or MCP replies | worker stdin only; tests search every state file, reply and error for it |
| Token not written by yt-dlp's cache | `cachedir=False`; verified against the real extractor (without it, `tokens.json` is created) |
| Bridge is local-only | binds `127.0.0.1`, 256-bit random secret in a per-user file, constant-time comparison |
| Only our extension talks to the host | browser `allowed_origins` plus a second origin check in the host; the ID is tested against the manifest key |
| Only this site | URL must be `https`, the DCH domain and a `film` / `concert` / `work` path, without user:password |
| Narrow MCP surface | only start / status / jobs; no shell, no arbitrary file access, no token; `start` is marked as a write |
| Expired tokens are not used | JWT expiry is checked before every call |
| No refresh token | by design, so a token has a limited lifetime (below) |

## Limitations

- **Token lifetime is unknown.** A multi-part concert may stop with "token rejected" part-way; finished parts stay, and `--item N` resumes.
- Quality: the yt-dlp extractor notes that 4K / FLAC streams are no longer offered; `--list` shows what your account really gets.
- DRM-protected or unavailable content is reported as such. Bypassing DRM is out of scope.
- Needs `ffmpeg` on `PATH`, and the computer, Brave and the network must be on.
- Web versions of ChatGPT / Claude are not supported: the token and files must not leave this computer, which would need an authenticated remote MCP server (plan phase 6, deliberately not built).
- The site's terms of use regarding downloads have not been reviewed. You are responsible for using this only for content your account may play.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| "The Brave bridge is not running" | Brave open and extension enabled; `python -m ytdlp_tool.dch_install status`; in `brave://extensions` open the extension's service worker and look for connection errors |
| "No Digital Concert Hall tab is open" | open the site in Brave and sign in |
| "N concert pages are open" | pass the URL explicitly |
| "Not signed in … no access token" | sign in, reload the page |
| "Access token has expired" / "rejected the token" | reload the site page (refreshes the token) and start again |
| Claude Desktop does not show the tools | fully quit and reopen it after `install` |
| Host log | `%LOCALAPPDATA%\ytdlp-tool\dch\host.log` |

## First real test (a few minutes, still to do)

1. `dch-start --list`: check the parts and the real quality.
2. `dch-start --item 1` on the shortest part, follow with `dch-status`, open the final file.
3. Note the time from reloading the page to an expiry error (the token lifetime).

## End-to-end test (developers)

`tests/e2e/run_dch_e2e.sh` (needs Node, Playwright and Xvfb) starts a real Chromium with the real extension on a fake digitalconcerthall.com page with a fake token, registers the host, then runs `dch-start` and the worker. Expected output: `E2E PASSED` (the worker gets the token from the browser, the real extractor tries it against the real server and receives 401 because it is fake).
