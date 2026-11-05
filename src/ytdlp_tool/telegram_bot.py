from __future__ import annotations
import argparse, json, os, sqlite3, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

MODES = {"audio", "video", "subs", "transcribe", "transcript", "choose", "txt", "srt",
         "ig_choose", "ig_caption", "ig_txt", "ig_srt", "ig_story", "x_post"}
ALIASES = {"igcaption": "ig_caption", "igtxt": "ig_txt",
           "igsrt": "ig_srt", "caption": "ig_caption",
           "tweet": "x_post", "x": "x_post", "xpost": "x_post"}
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
X_HOSTS = {"x.com", "www.x.com", "mobile.x.com", "twitter.com",
           "www.twitter.com", "mobile.twitter.com"}
HOSTS = YOUTUBE_HOSTS | INSTAGRAM_HOSTS | X_HOSTS | {"vimeo.com", "www.vimeo.com"}

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
                else "/x_post" if host in X_HOSTS else "/audio")
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
            if mode == "x_post":
                if u.hostname not in X_HOSTS:
                    return None
                from .x_twitter import validate_status_url
                try:
                    validate_status_url(parts[1])
                except ValueError:
                    return None
            if u.hostname in INSTAGRAM_HOSTS:
                import re
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
    import uuid
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
    import uuid

    paths = tuple(Path(p) for p in paths)
    if not paths:
        raise ValueError("No Instagram media to send")

    types = {".jpg": "photo", ".jpeg": "photo", ".png": "photo",
             ".mp4": "video"}
    for start in range(0, len(paths), 10):
        batch = paths[start:start + 10]
        items = []
        for n, path in enumerate(batch):
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

        def field(name, value):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")

        chunks.append(field("chat_id", chat))
        if len(items) == 1:
            kind, _ = items[0]
            method = "sendPhoto" if kind == "photo" else "sendVideo"
        else:
            method = "sendMediaGroup"
            media = [
                {"type": kind, "media": f"attach://media{i}"}
                for i, (kind, _) in enumerate(items)
            ]
            chunks.append(field("media", json.dumps(media, separators=(",", ":"))))
        for i, (kind, path) in enumerate(items):
            field_name = f"media{i}" if len(items) > 1 else kind
            media_type = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else (
                "image/png" if kind == "photo" else "video/mp4"
            )
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
    """Native Telegram photo/video or album; reuse the verified uploader."""
    return send_instagram_media(token, chat, paths)


def setup(db):
    db.execute("CREATE TABLE IF NOT EXISTS jobs (update_id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, mode TEXT NOT NULL, url TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', error TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS format_choices (request_id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, requester INTEGER NOT NULL, url TEXT NOT NULL, selected TEXT)")
    db.commit()

def ingest_callback(db, item):
    """Queue exactly one format selection for the original requesting user."""
    import re
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
    if chat is None: return
    raw = msg.get("text", "")
    parsed = parse(raw)
    if parsed is None:
        import re
        candidate = re.search(r'https://(?:(?:www|mobile)\.)?(?:youtu\.be|youtube\.com|vimeo\.com|instagram\.com|x\.com|twitter\.com)/[^\s<>]+', raw, re.I)
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--root", default=str(Path.home()/".ytdlp-telegram"))
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("YTDL_TELEGRAM_BOT_TOKEN")
    if not token: ap.error("YTDL_TELEGRAM_BOT_TOKEN is required")
    allowed = {x.strip() for x in os.environ.get("YTDL_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}
    if not allowed: ap.error("YTDL_ALLOWED_CHAT_IDS is required; public execution disabled")
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root/"jobs.sqlite") as db:
        setup(db)
        while True:
            job = db.execute("SELECT update_id,chat,mode,url FROM jobs WHERE state='pending' ORDER BY update_id LIMIT 1").fetchone()
            if not job:
                offset = db.execute("SELECT COALESCE(MAX(update_id),0)+1 FROM jobs").fetchone()[0]
                updates = api(token, "getUpdates", {"offset": offset, "timeout": 20, "allowed_updates": '["message","callback_query"]'})
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
                            except Exception:
                                pass
                    else:
                        # Record rejected IDs so polling offset advances without allowing work.
                        db.execute("INSERT OR IGNORE INTO jobs(update_id,chat,mode,url,state) VALUES (?,?,?,?,?)",
                                   (update["update_id"], 0, "rejected", "", "done"))
                        db.commit()
            else:
                uid, chat, mode, url = job
                try:
                    job_failure = None
                    if mode == "help":
                        send(token, chat, "Paste a public Instagram or X/Twitter post URL for native photo/video followed by authored text in a separate message (no TXT attachment). For speech use /igtxt URL or /igsrt URL; optional menu: /ig_choose URL. YouTube: TXT or SRT choice. Instagram Stories often have overlay text requiring OCR and login.")
                    elif mode == "invalid":
                        send(token, chat, "Unsupported link. Send an Instagram /reel/ or /p/ link, or a YouTube video link.")
                    elif mode == "ig_story":
                        send(token, chat, "Instagram Story: there is generally no separate written post caption to retrieve from public metadata. Text displayed on a Story is embedded in its image/video, requiring OCR; Stories commonly require login. No audio, video or OCR was processed.")
                    elif mode == "x_post":
                        folder = root/"downloads"/str(uid)
                        folder.mkdir(parents=True, exist_ok=True)
                        command = [args.python, "-m", "ytdlp_tool", "x-post", url,
                                   "--output-dir", str(folder)]
                        proc = subprocess.run(
                            command, capture_output=True, text=True, timeout=180,
                            encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                        )
                        if proc.returncode:
                            raise RuntimeError("X post unavailable: " + (proc.stderr or "retrieval failed")[-250:])
                        text_files = list(folder.glob("tweet-*.txt"))
                        if len(text_files) != 1:
                            raise RuntimeError("X post text result missing")
                        media_paths = sorted(
                            (p for p in folder.rglob("*") if p.is_file()
                             and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".mp4"}),
                            key=lambda p: str(p),
                        )
                        if media_paths:
                            try:
                                send_native_media(token, chat, media_paths)
                            except Exception as exc:
                                send(token, chat, "X media could not be delivered: " + str(exc)[-180:])
                        warnings = [line[9:].strip() for line in proc.stdout.splitlines()
                                    if line.startswith("Warning: ")]
                        if warnings:
                            send(token, chat, "Some X media unavailable: " + "; ".join(warnings)[-300:])
                        written = text_files[0].read_text(encoding="utf-8").strip()
                        if written:
                            send_caption_text(token, chat, written)
                        elif media_paths:
                            send(token, chat, "This X post has no authored text.")
                        else:
                            raise RuntimeError("X post contains neither accessible text nor media")
                    elif mode == "ig_caption":
                        # A bare Instagram link produces two separate Telegram
                        # deliveries: native media and ordinary caption text.
                        # Intermediate TXT remains Ops-local; never upload it.
                        folder = root/"downloads"/str(uid)
                        folder.mkdir(parents=True, exist_ok=True)
                        base = [args.python, "-m", "ytdlp_tool"]
                        run_args = {
                            "capture_output": True, "text": True, "timeout": 180,
                            "encoding": "utf-8", "errors": "replace",
                            "env": {**os.environ, "PYTHONIOENCODING": "utf-8"},
                        }
                        caption_proc = subprocess.run(
                            base + ["ig-caption", url, "--output-dir", str(folder)],
                            **run_args,
                        )
                        caption_paths = list(folder.glob("instagram-*-caption.txt"))
                        written = (
                            caption_paths[0].read_text(encoding="utf-8").strip()
                            if caption_proc.returncode == 0 and len(caption_paths) == 1
                            else ""
                        )
                        media_proc = subprocess.run(
                            base + ["ig-media", url, "--output-dir", str(folder)],
                            **run_args,
                        )
                        media_paths = sorted(
                            (p for p in folder.rglob("*")
                             if p.is_file() and p.suffix.lower() in
                             {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webm"}),
                            key=lambda p: str(p),
                        )
                        media_error = None
                        try:
                            if media_proc.returncode:
                                detail = (media_proc.stderr or "media not accessible")[-220:]
                                raise RuntimeError(detail)
                            send_instagram_media(token, chat, media_paths)
                        except Exception as media_exc:
                            media_error = str(media_exc)[-230:]
                            send(token, chat, "Instagram media unavailable: " + media_error)
                        if written:
                            send_caption_text(token, chat, written)
                        else:
                            detail = (caption_proc.stderr or "no written caption available")[-220:]
                            send(token, chat, "Instagram written caption unavailable: " + detail)
                            if media_error is not None:
                                job_failure = (
                                    "Instagram media and written caption unavailable: " +
                                    media_error + "; caption: " + detail
                                )[:300]
                    elif mode in {"choose", "ig_choose"}:
                        choice = db.execute(
                            "SELECT requester FROM format_choices WHERE request_id=? AND chat=?",
                            (uid, chat),
                        ).fetchone()
                        if not choice:
                            raise RuntimeError("Format selection requires an identified sender")
                        if mode == "ig_choose":
                            send(token, chat, "Instagram: choose post caption or spoken transcript format:",
                                 keyboard=format_keyboard(uid, "instagram"))
                        else:
                            send(token, chat, "Choose original-language transcript format:",
                                 keyboard=format_keyboard(uid))
                    else:
                        if mode != "ig_caption":
                            send(token, chat, "Job accepted: " + str(uid))
                        folder = root/"downloads"/str(uid)
                        folder.mkdir(parents=True, exist_ok=True)
                        command_mode = {
                            "txt": "transcript", "srt": "transcript",
                            "ig_caption": "ig-caption",
                            "ig_txt": "ig-speech", "ig_srt": "ig-speech",
                        }.get(mode, mode)
                        cmd = [args.python, "-m", "ytdlp_tool", command_mode, url,
                               "--output-dir", str(folder)]
                        if command_mode in ("transcribe", "transcript", "ig-speech"):
                            cmd += ["--model", "large-v3", "--model-dir", args.model_dir]
                        if mode in ("txt", "srt", "ig_txt", "ig_srt"):
                            cmd += ["--format", "srt" if mode.endswith("srt") else "txt"]
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                        if proc.returncode: raise RuntimeError((proc.stderr or "processing failed")[-300:])
                        names = [p for p in folder.rglob("*") if p.is_file()]
                        if command_mode in ("transcribe", "transcript", "ig-caption", "ig-speech"):
                            names = [p for p in names if p.suffix in (".srt", ".txt")]
                        if mode in ("txt", "srt", "ig_caption", "ig_txt", "ig_srt"):
                            selected_ext = "srt" if mode.endswith("srt") else "txt"
                            names = [p for p in names if p.suffix == "." + selected_ext]
                        if not names: raise RuntimeError("No output files produced")
                        if mode == "ig_caption":
                            if len(names) != 1:
                                raise RuntimeError("Expected exactly one caption text file")
                            caption_text = names[0].read_text(encoding="utf-8").strip()
                            if not caption_text:
                                raise RuntimeError("Instagram caption is empty")
                            send_caption_text(token, chat, caption_text)
                        for path in names[:4]:
                            upload(token, chat, path)
                        source = next((line[8:].strip() for line in proc.stdout.splitlines() if line.startswith("Source: ")), None)
                        source_label = ("; source=" + source) if source else ""
                        if mode != "ig_caption":
                            send(token, chat, "Completed job " + str(uid) + source_label)
                    db.execute(
                        "UPDATE jobs SET state=?,error=? WHERE update_id=?",
                        ("failed" if job_failure else "done", job_failure, uid),
                    )
                except Exception as exc:
                    db.execute("UPDATE jobs SET state='failed',error=? WHERE update_id=?", (str(exc)[:300],uid))
                    notice = "Job failed. Contact operator."
                    if mode == "transcript":
                        detail = str(exc).lower()
                        if "timed out" in detail or "timeout" in detail:
                            notice = "YouTube transcript download timed out. Captions may exist; ASR was not run."
                        elif "403" in detail or "429" in detail or "forbidden" in detail:
                            notice = "YouTube captions were blocked or rate-limited. ASR was not run."
                    elif mode in {"ig_caption", "ig_txt", "ig_srt"}:
                        detail = str(exc).lower()
                        if any(term in detail for term in ("403", "429", "login", "private", "rate-limit", "forbidden")):
                            notice = "Instagram access denied or rate-limited. This bot supports only accessible public posts, without bypassing login."
                        elif "caption is absent" in detail:
                            notice = "This Instagram post has no accessible written caption."
                        elif "no speech detected" in detail:
                            notice = "No recognizable spoken audio in this Instagram video."
                        elif "timed out" in detail:
                            notice = "Instagram retrieval or speech recognition timed out."
                    try: send(token, chat, notice)
                    except Exception: pass
                db.commit()
            if args.once: break

if __name__ == "__main__":
    main()
