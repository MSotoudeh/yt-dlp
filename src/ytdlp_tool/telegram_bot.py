from __future__ import annotations
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

MODES = {"audio", "video", "subs", "transcribe", "transcript", "choose", "txt", "srt",
         "ig_choose", "ig_caption", "ig_txt", "ig_srt", "ig_story", "x_post", "li_post"}
ALIASES = {"igcaption": "ig_caption", "igtxt": "ig_txt",
           "igsrt": "ig_srt", "caption": "ig_caption",
           "tweet": "x_post", "x": "x_post", "xpost": "x_post",
           "linkedin": "li_post", "li": "li_post", "lipost": "li_post"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
X_HOSTS = {"x.com", "www.x.com", "mobile.x.com", "twitter.com",
           "www.twitter.com", "mobile.twitter.com"}
LINKEDIN_HOSTS = {"linkedin.com", "www.linkedin.com", "it.linkedin.com",
                  "de.linkedin.com", "fr.linkedin.com", "uk.linkedin.com"}
HOSTS = YOUTUBE_HOSTS | INSTAGRAM_HOSTS | X_HOSTS | LINKEDIN_HOSTS | {"vimeo.com", "www.vimeo.com"}

def parse(text):
    parts = text.strip().split(maxsplit=1)
    if parts and parts[0].split("@")[0] in ("/help", "/start"):
        return "help", ""
    if len(parts) == 1 and parts[0].startswith('https://'):
        try:
            host = urlsplit(parts[0]).hostname
        except ValueError:
            return None
        mode = ("/choose" if host in YOUTUBE_HOSTS
                else "/ig_caption" if host in INSTAGRAM_HOSTS
                else "/x_post" if host in X_HOSTS
                else "/li_post" if host in LINKEDIN_HOSTS else "/audio")
        parts = [mode, parts[0]]
    if len(parts) != 2:
        return None
    mode = parts[0].split("@")[0].lstrip("/").lower()
    mode = ALIASES.get(mode, mode)
    try:
        u = urlsplit(parts[1])
        if mode in MODES and u.scheme == "https" and u.hostname in HOSTS and u.port in (None, 443) and not u.username and not u.password:
            if mode in {"choose", "txt", "srt", "transcript", "subs"} and u.hostname not in YOUTUBE_HOSTS:
                return None
            if mode == "li_post":
                if u.hostname not in LINKEDIN_HOSTS:
                    return None
                from .linkedin import validate_post_url
                try:
                    validate_post_url(parts[1])
                except ValueError:
                    return None
            if mode == "x_post":
                if u.hostname not in X_HOSTS:
                    return None
                from .x_twitter import validate_status_url
                try:
                    validate_status_url(parts[1])
                except ValueError:
                    return None
            if u.hostname in INSTAGRAM_HOSTS:
                is_story = bool(re.fullmatch(
                    r"/stories/[A-Za-z0-9._]+/[0-9]+/?", u.path
                ))
                if is_story:
                    if mode == "ig_caption" or mode == "ig_story":
                        return "ig_story", parts[1]
                    return None
            if mode in {"ig_choose", "ig_caption", "ig_txt", "ig_srt", "ig_story"}:
                if u.hostname not in INSTAGRAM_HOSTS or mode == "ig_story":
                    return None
                from .instagram import validate_instagram_url
                try:
                    validate_instagram_url(parts[1])
                except ValueError:
                    return None
            return mode, parts[1]
    except ValueError:
        pass
    return None

def api(token, method, params):
    body = urlencode(params).encode()
    req = Request("https://api.telegram.org/bot" + token + "/" + method, data=body)
    with urlopen(req, timeout=55) as f:
        data = json.load(f)
    if not data.get("ok"):
        raise RuntimeError("Telegram API failed")
    return data["result"]

def send(token, chat, text, *, keyboard=None):
    params = {"chat_id": chat, "text": text[:4000]}
    if keyboard is not None:
        params["reply_markup"] = json.dumps(keyboard)
    return api(token, "sendMessage", params)


def format_keyboard(request_id, platform="youtube"):
    if platform == "instagram":
        return {"inline_keyboard": [
            [{"text": "Caption - Post description", "callback_data": f"fmt:ig_caption:{request_id}"}],
            [
                {"text": "Speech TXT", "callback_data": f"fmt:ig_txt:{request_id}"},
                {"text": "Speech SRT", "callback_data": f"fmt:ig_srt:{request_id}"},
            ],
        ]}
    return {"inline_keyboard": [[
        {"text": "TXT - Plain text", "callback_data": f"fmt:txt:{request_id}"},
        {"text": "SRT - Timed subtitles", "callback_data": f"fmt:srt:{request_id}"},
    ]]}

def send_caption_text(token, chat, caption):
    """Send full original Unicode caption without Telegram's 4096 UTF-16 limit truncation."""
    if not caption:
        raise ValueError("Cannot send an empty caption")
    # 1800 code points are < 4096 UTF-16 units, even if every char is astral.
    for pos in range(0, len(caption), 1800):
        send(token, chat, caption[pos:pos + 1800])


def upload(token, chat, path):
    if path.stat().st_size > 49 * 1024 * 1024:
        send(token, chat, "Output exceeds Telegram direct upload limit (50 MB): " + path.name)
        return
    boundary = "ytdlp_" + uuid.uuid4().hex
    prefix = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat}\r\n"
              f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\n"
              "Content-Type: application/octet-stream\r\n\r\n").encode()
    suffix = ("\r\n--" + boundary + "--\r\n").encode()
    body = prefix + path.read_bytes() + suffix
    req = Request("https://api.telegram.org/bot" + token + "/sendDocument", data=body,
                  headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urlopen(req, timeout=120) as f:
        result = json.load(f)
    if not result.get("ok"):
        raise RuntimeError("Telegram sendDocument failed")


def send_instagram_media(token, chat, paths):
    """Send original media as native Telegram photo/video or album, never as document."""
    paths = tuple(Path(p) for p in paths)
    if not paths:
        raise ValueError("No Instagram media to send")

    types = {".jpg": "photo", ".jpeg": "photo", ".png": "photo",
             ".mp4": "video", ".gif": "animation"}
    for start in range(0, len(paths), 10):
        batch = paths[start:start + 10]
        items = []
        for path in batch:
            kind = types.get(path.suffix.lower())
            if not kind:
                raise ValueError(f"Unsupported Telegram photo/video format: {path.suffix}")
            if not path.is_file():
                raise FileNotFoundError(path)
            limit = 10 * 1024 * 1024 if kind == "photo" else 49 * 1024 * 1024
            if path.stat().st_size > limit:
                raise ValueError(f"Instagram {kind} exceeds Telegram upload limit: {path.name}")
            items.append((kind, path))
        boundary = "ig_" + uuid.uuid4().hex
        chunks = []

        def field(name, value, boundary=boundary):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")

        chunks.append(field("chat_id", chat))
        if len(items) == 1:
            kind, _ = items[0]
            method = {"photo": "sendPhoto", "video": "sendVideo", "animation": "sendAnimation"}[kind]
        else:
            if any(kind == "animation" for kind, _ in items):
                raise ValueError("Telegram media groups cannot include GIF animations")
            method = "sendMediaGroup"
            media = [
                {"type": kind, "media": f"attach://media{i}"}
                for i, (kind, _) in enumerate(items)
            ]
            chunks.append(field("media", json.dumps(media, separators=(",", ":"))))
        for i, (kind, path) in enumerate(items):
            field_name = f"media{i}" if len(items) > 1 else kind
            media_type = ("image/gif" if kind == "animation" else
                          "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else
                          "image/png" if kind == "photo" else "video/mp4")
            # Avoid non-ASCII header filename encoding, which fails for Instagram
            # captions/titles with Unicode punctuation on Windows.
            filename = f"instagram-{i}{path.suffix.lower()}"
            chunks.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                f"Content-Type: {media_type}\r\n\r\n".encode("ascii")
            )
            chunks.append(path.read_bytes())
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("ascii"))
        req = Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=b"".join(chunks),
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        )
        with urlopen(req, timeout=180) as response:
            data = json.load(response)
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed")


def send_native_media(token, chat, paths):
    """Send native photos/videos in order; animated GIFs individually (Telegram limitation)."""
    batch = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() == ".gif":
            if batch:
                send_instagram_media(token, chat, batch)
                batch.clear()
            send_instagram_media(token, chat, [path])
        else:
            batch.append(path)
    if batch:
        send_instagram_media(token, chat, batch)


def setup(db):
    db.execute("CREATE TABLE IF NOT EXISTS jobs (update_id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, mode TEXT NOT NULL, url TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', error TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS format_choices (request_id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, requester INTEGER NOT NULL, url TEXT NOT NULL, selected TEXT)")
    db.commit()

def ingest_callback(db, item):
    """Queue exactly one format selection for the original requesting user."""
    callback = item.get("callback_query") or {}
    uid = item["update_id"]
    chat = (callback.get("message") or {}).get("chat") or {}
    chat_id = chat.get("id")
    sender = (callback.get("from") or {}).get("id")
    match = re.fullmatch(r"fmt:(txt|srt|ig_caption|ig_txt|ig_srt):([0-9]+)", callback.get("data") or "")
    message = "Invalid or expired format selection."
    selected = None
    if match and chat_id is not None and sender is not None:
        fmt, original_id = match.group(1), int(match.group(2))
        choice = db.execute(
            "SELECT chat,requester,url,selected FROM format_choices WHERE request_id=?",
            (original_id,),
        ).fetchone()
        choice_host = urlsplit(choice[2]).hostname if choice else None
        matching_platform = (
            (fmt in {"txt", "srt"} and choice_host in YOUTUBE_HOSTS)
            or (fmt in {"ig_caption", "ig_txt", "ig_srt"} and choice_host in INSTAGRAM_HOSTS)
        )
        if choice and choice[0] == chat_id and choice[1] == sender and matching_platform:
            if choice[3]:
                message = "A format has already been selected for this link."
            else:
                change = db.execute(
                    "UPDATE format_choices SET selected=? WHERE request_id=? AND selected IS NULL",
                    (fmt, original_id),
                )
                if change.rowcount == 1:
                    db.execute(
                        "INSERT OR IGNORE INTO jobs(update_id,chat,mode,url) VALUES (?,?,?,?)",
                        (uid, chat_id, fmt, choice[2]),
                    )
                    selected = fmt
                    message = "Format " + fmt.upper() + " selected."
                else:
                    message = "A format has already been selected for this link."
    if not selected:
        db.execute(
            "INSERT OR IGNORE INTO jobs(update_id,chat,mode,url,state) VALUES (?,?,?,?,?)",
            (uid, chat_id or 0, "ignored", "", "done"),
        )
    db.commit()
    return message


def ingest(db, item):
    if item.get("callback_query"):
        return ingest_callback(db, item)
    uid = item["update_id"]
    msg = item.get("message") or {}
    chat = (msg.get("chat") or {}).get("id")
    if chat is None:
        return
    raw = msg.get("text", "")
    parsed = parse(raw)
    if parsed is None:
        candidate = re.search(r'https://(?:(?:www|mobile|[a-z]{2,3})\.)?(?:youtu\.be|youtube\.com|vimeo\.com|instagram\.com|x\.com|twitter\.com|linkedin\.com)/[^\s<>]+', raw, re.I)
        if candidate:
            parsed = parse(candidate.group(0))
    parsed = parsed or ("invalid", "")
    db.execute("INSERT OR IGNORE INTO jobs(update_id,chat,mode,url) VALUES (?,?,?,?)", (uid, chat, *parsed))
    if parsed[0] in {"choose", "ig_choose"}:
        requester = (msg.get("from") or {}).get("id")
        if requester is None and (msg.get("chat") or {}).get("type") == "private":
            requester = chat
        if requester is not None:
            db.execute(
                "INSERT OR IGNORE INTO format_choices(request_id,chat,requester,url) VALUES (?,?,?,?)",
                (uid, chat, requester, parsed[1]),
            )
    db.commit()


# --------------------------------------------------------------------------- #
# Job processing
# --------------------------------------------------------------------------- #

NATIVE_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".mp4", ".gif"}
X_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".mp4"}
INSTAGRAM_MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm"}

HELP_TEXT = (
    "Paste a public Instagram, X/Twitter or LinkedIn post URL for native photo/video followed by "
    "authored text in a separate message (no TXT attachment). For speech use /igtxt URL or /igsrt URL; "
    "optional menu: /ig_choose URL. YouTube: TXT or SRT choice. Instagram Stories often have overlay "
    "text requiring OCR and login."
)
INVALID_TEXT = (
    "Unsupported link. Send an Instagram post/Reel, X/Twitter status, LinkedIn public post or YouTube link."
)
STORY_TEXT = (
    "Instagram Story: there is generally no separate written post caption to retrieve from public "
    "metadata. Text displayed on a Story is embedded in its image/video, requiring OCR; Stories commonly "
    "require login. No audio, video or OCR was processed."
)


_LOG_FILE = None


def _log(message):
    """Timestamped log line to stderr (and --log-file). Never pass tokens or message bodies to it."""
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    print(line, file=sys.stderr, flush=True)
    if _LOG_FILE is not None:
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass  # logging must never take the bot down


@dataclass
class JobContext:
    """Everything a job handler needs; keeps handlers free of module-level state."""
    token: str
    db: sqlite3.Connection
    root: Path
    python: str
    model_dir: str


def _run_cli(cmd, timeout):
    """Run one ytdlp_tool sub-command with UTF-8 output captured."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _job_folder(ctx, uid):
    folder = ctx.root / "downloads" / str(uid)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _media_files(folder, extensions):
    return sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in extensions),
        key=str,
    )


def _warnings(proc):
    """Collect 'Warning: ...' lines a ytdlp_tool sub-command printed on stdout."""
    return [line[9:].strip() for line in proc.stdout.splitlines() if line.startswith("Warning: ")]


def _handle_li_post(ctx, uid, chat, url):
    folder = _job_folder(ctx, uid)
    proc = _run_cli([ctx.python, "-m", "ytdlp_tool", "li-post", url, "--output-dir", str(folder)], 240)
    if proc.returncode:
        raise RuntimeError("LinkedIn post unavailable: " + (proc.stderr or "retrieval failed")[-240:])
    text_files = list(folder.glob("linkedin-*.txt"))
    if len(text_files) != 1:
        raise RuntimeError("LinkedIn post text result missing")
    failure = None
    media_paths = _media_files(folder, NATIVE_MEDIA_EXTS)
    if media_paths:
        try:
            send_native_media(ctx.token, chat, media_paths)
        except Exception as exc:
            failure = "LinkedIn media delivery failed: " + str(exc)[-210:]
            send(ctx.token, chat, "LinkedIn media could not be delivered: " + str(exc)[-180:])
    warnings = _warnings(proc)
    if warnings:
        send(ctx.token, chat, "Some LinkedIn media unavailable or hidden: " + "; ".join(warnings)[-450:])
    authored = text_files[0].read_text(encoding="utf-8").strip()
    if authored:
        send_caption_text(ctx.token, chat, authored)
    elif media_paths:
        send(ctx.token, chat, "This LinkedIn post has no accessible written text.")
    else:
        raise RuntimeError("LinkedIn post contains neither accessible text nor media")
    return failure


def _handle_x_post(ctx, uid, chat, url):
    folder = _job_folder(ctx, uid)
    proc = _run_cli([ctx.python, "-m", "ytdlp_tool", "x-post", url, "--output-dir", str(folder)], 180)
    if proc.returncode:
        raise RuntimeError("X post unavailable: " + (proc.stderr or "retrieval failed")[-250:])
    text_files = list(folder.glob("tweet-*.txt"))
    if len(text_files) != 1:
        raise RuntimeError("X post text result missing")
    media_paths = _media_files(folder, X_MEDIA_EXTS)
    if media_paths:
        try:
            send_native_media(ctx.token, chat, media_paths)
        except Exception as exc:
            send(ctx.token, chat, "X media could not be delivered: " + str(exc)[-180:])
    warnings = _warnings(proc)
    if warnings:
        send(ctx.token, chat, "Some X media unavailable: " + "; ".join(warnings)[-300:])
    written = text_files[0].read_text(encoding="utf-8").strip()
    if written:
        send_caption_text(ctx.token, chat, written)
    elif media_paths:
        send(ctx.token, chat, "This X post has no authored text.")
    else:
        raise RuntimeError("X post contains neither accessible text nor media")
    return None


def _handle_ig_caption(ctx, uid, chat, url):
    """A bare Instagram link yields two separate Telegram deliveries: native media, then caption text.

    The intermediate TXT stays on Ops; it is never uploaded.
    """
    folder = _job_folder(ctx, uid)
    base = [ctx.python, "-m", "ytdlp_tool"]
    caption_proc = _run_cli(base + ["ig-caption", url, "--output-dir", str(folder)], 180)
    caption_paths = list(folder.glob("instagram-*-caption.txt"))
    written = (
        caption_paths[0].read_text(encoding="utf-8").strip()
        if caption_proc.returncode == 0 and len(caption_paths) == 1
        else ""
    )
    media_proc = _run_cli(base + ["ig-media", url, "--output-dir", str(folder)], 180)
    media_paths = _media_files(folder, INSTAGRAM_MEDIA_EXTS)
    media_error = None
    try:
        if media_proc.returncode:
            raise RuntimeError((media_proc.stderr or "media not accessible")[-220:])
        send_instagram_media(ctx.token, chat, media_paths)
    except Exception as media_exc:
        media_error = str(media_exc)[-230:]
        send(ctx.token, chat, "Instagram media unavailable: " + media_error)
    if written:
        send_caption_text(ctx.token, chat, written)
        return None
    detail = (caption_proc.stderr or "no written caption available")[-220:]
    send(ctx.token, chat, "Instagram written caption unavailable: " + detail)
    if media_error is not None:
        return ("Instagram media and written caption unavailable: " + media_error + "; caption: " + detail)[:300]
    return None


def _handle_choose(ctx, uid, chat, mode):
    choice = ctx.db.execute(
        "SELECT requester FROM format_choices WHERE request_id=? AND chat=?", (uid, chat),
    ).fetchone()
    if not choice:
        raise RuntimeError("Format selection requires an identified sender")
    if mode == "ig_choose":
        send(ctx.token, chat, "Instagram: choose post caption or spoken transcript format:",
             keyboard=format_keyboard(uid, "instagram"))
    else:
        send(ctx.token, chat, "Choose original-language transcript format:", keyboard=format_keyboard(uid))
    return None


def _handle_download(ctx, uid, chat, mode, url):
    """audio / video / subs / transcribe / transcript / txt / srt / ig_txt / ig_srt."""
    send(ctx.token, chat, "Job accepted: " + str(uid))
    folder = _job_folder(ctx, uid)
    command_mode = {
        "txt": "transcript", "srt": "transcript",
        "ig_txt": "ig-speech", "ig_srt": "ig-speech",
    }.get(mode, mode)
    cmd = [ctx.python, "-m", "ytdlp_tool", command_mode, url, "--output-dir", str(folder)]
    if command_mode in ("transcribe", "transcript", "ig-speech"):
        cmd += ["--model", "large-v3", "--model-dir", ctx.model_dir]
    if mode in ("txt", "srt", "ig_txt", "ig_srt"):
        cmd += ["--format", "srt" if mode.endswith("srt") else "txt"]
    proc = _run_cli(cmd, 3600)
    if proc.returncode:
        raise RuntimeError((proc.stderr or "processing failed")[-300:])
    names = [p for p in folder.rglob("*") if p.is_file()]
    if command_mode in ("transcribe", "transcript", "ig-speech"):
        names = [p for p in names if p.suffix in (".srt", ".txt")]
    if mode in ("txt", "srt", "ig_txt", "ig_srt"):
        selected_ext = "srt" if mode.endswith("srt") else "txt"
        names = [p for p in names if p.suffix == "." + selected_ext]
    if not names:
        raise RuntimeError("No output files produced")
    for path in names[:4]:
        upload(ctx.token, chat, path)
    source = next((line[8:].strip() for line in proc.stdout.splitlines() if line.startswith("Source: ")), None)
    send(ctx.token, chat, "Completed job " + str(uid) + (("; source=" + source) if source else ""))
    return None


def dispatch_job(ctx, uid, chat, mode, url):
    """Run one job. Returns a failure description for a partially failed job, else None."""
    if mode == "help":
        send(ctx.token, chat, HELP_TEXT)
    elif mode == "invalid":
        send(ctx.token, chat, INVALID_TEXT)
    elif mode == "ig_story":
        send(ctx.token, chat, STORY_TEXT)
    elif mode == "li_post":
        return _handle_li_post(ctx, uid, chat, url)
    elif mode == "x_post":
        return _handle_x_post(ctx, uid, chat, url)
    elif mode == "ig_caption":
        return _handle_ig_caption(ctx, uid, chat, url)
    elif mode in {"choose", "ig_choose"}:
        return _handle_choose(ctx, uid, chat, mode)
    else:
        return _handle_download(ctx, uid, chat, mode, url)
    return None


def failure_notice(mode, exc):
    """User-facing text for a failed job. Deliberately generic: details stay in the job row and log."""
    detail = str(exc).lower()
    if mode == "transcript":
        if "timed out" in detail or "timeout" in detail:
            return "YouTube transcript download timed out. Captions may exist; ASR was not run."
        if "403" in detail or "429" in detail or "forbidden" in detail:
            return "YouTube captions were blocked or rate-limited. ASR was not run."
    elif mode in {"ig_caption", "ig_txt", "ig_srt"}:
        if any(term in detail for term in ("403", "429", "login", "private", "rate-limit", "forbidden")):
            return ("Instagram access denied or rate-limited. This bot supports only accessible public "
                    "posts, without bypassing login.")
        if "caption is absent" in detail:
            return "This Instagram post has no accessible written caption."
        if "no speech detected" in detail:
            return "No recognizable spoken audio in this Instagram video."
        if "timed out" in detail:
            return "Instagram retrieval or speech recognition timed out."
    return "Job failed. Contact operator."


def process_job(ctx, job):
    uid, chat, mode, url = job
    _log(f"job {uid} mode={mode} started")
    try:
        failure = dispatch_job(ctx, uid, chat, mode, url)
        ctx.db.execute(
            "UPDATE jobs SET state=?,error=? WHERE update_id=?",
            ("failed" if failure else "done", failure, uid),
        )
        _log(f"job {uid} mode={mode} {'failed: ' + failure if failure else 'done'}")
    except Exception as exc:
        ctx.db.execute("UPDATE jobs SET state='failed',error=? WHERE update_id=?", (str(exc)[:300], uid))
        _log(f"job {uid} mode={mode} failed: {str(exc)[:300]}")
        try:
            send(ctx.token, chat, failure_notice(mode, exc))
        except Exception as send_exc:
            _log(f"job {uid}: could not notify chat ({type(send_exc).__name__})")
    ctx.db.commit()


# --------------------------------------------------------------------------- #
# Polling loop
# --------------------------------------------------------------------------- #

def _ingest_updates(token, db, allowed, updates):
    for update in updates:
        payload = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
        chat_id = str((payload.get("chat") or {}).get("id", ""))
        if chat_id in allowed or "*" in allowed:
            response = ingest(db, update)
            if update.get("callback_query"):
                try:
                    api(token, "answerCallbackQuery", {
                        "callback_query_id": update["callback_query"]["id"],
                        "text": response or "Format selected.",
                    })
                except Exception as exc:
                    _log(f"answerCallbackQuery failed ({type(exc).__name__})")
        else:
            # Record rejected IDs so the polling offset advances without allowing work.
            db.execute("INSERT OR IGNORE INTO jobs(update_id,chat,mode,url,state) VALUES (?,?,?,?,?)",
                       (update["update_id"], 0, "rejected", "", "done"))
            db.commit()


def load_allowlist():
    """Chat IDs allowed to use the bot; a wildcard needs an explicit opt-in."""
    allowed = {x.strip() for x in os.environ.get("YTDL_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
    if not allowed:
        raise SystemExit("YTDL_ALLOWED_CHAT_IDS is required; public execution disabled")
    if "*" in allowed and os.environ.get("YTDL_ALLOW_PUBLIC_BOT") != "1":
        raise SystemExit(
            "YTDL_ALLOWED_CHAT_IDS='*' would let anyone run downloads on this machine. "
            "Set YTDL_ALLOW_PUBLIC_BOT=1 to confirm that this is intended."
        )
    return allowed


def main():
    ap = argparse.ArgumentParser(description="Private Telegram front-end for ytdlp-tool")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--root", default=str(Path.home() / ".ytdlp-telegram"))
    ap.add_argument("--once", action="store_true", help="process at most one polling/job step, then exit")
    ap.add_argument("--log-file", default=None, help="also append log lines to this file")
    args = ap.parse_args()
    global _LOG_FILE
    _LOG_FILE = args.log_file
    token = os.environ.get("YTDL_TELEGRAM_BOT_TOKEN")
    if not token:
        ap.error("YTDL_TELEGRAM_BOT_TOKEN is required")
    allowed = load_allowlist()
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    poll_failures = 0
    _log("bot starting")
    with sqlite3.connect(root / "jobs.sqlite") as db:
        setup(db)
        ctx = JobContext(token=token, db=db, root=root, python=args.python, model_dir=args.model_dir)
        while True:
            job = db.execute(
                "SELECT update_id,chat,mode,url FROM jobs WHERE state='pending' ORDER BY update_id LIMIT 1"
            ).fetchone()
            if job:
                process_job(ctx, job)
            else:
                offset = db.execute("SELECT COALESCE(MAX(update_id),0)+1 FROM jobs").fetchone()[0]
                try:
                    updates = api(token, "getUpdates", {
                        "offset": offset, "timeout": 20, "allowed_updates": '["message","callback_query"]',
                    })
                    if poll_failures:
                        _log(f"getUpdates recovered after {poll_failures} failure(s)")
                    poll_failures = 0
                except (OSError, ValueError, RuntimeError) as exc:
                    # Transient network/Telegram errors must not kill the bot: the scheduled task only
                    # restarts it a few times, so back off and retry in-process instead. Only the
                    # exception type is logged; urllib messages are not guaranteed token-free.
                    poll_failures += 1
                    _log(f"getUpdates failed ({type(exc).__name__}, attempt {poll_failures}); retrying")
                    if args.once:
                        raise
                    time.sleep(min(60, 2 ** min(poll_failures, 6)))
                    continue
                _ingest_updates(token, db, allowed, updates)
            if args.once:
                break


def run():
    """Entry point for ``python -m ytdlp_tool.telegram_bot``: log why the bot stopped, then exit non-zero."""
    try:
        main()
    except KeyboardInterrupt:
        _log("bot stopped (interrupted)")
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception:
        _log("bot crashed:\n" + traceback.format_exc())
        raise SystemExit(1) from None


if __name__ == "__main__":
    run()
