from __future__ import annotations
import argparse, json, os, sqlite3, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

MODES = {"audio", "video", "subs", "transcribe"}
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "vimeo.com", "www.vimeo.com"}

def parse(text):
    parts = text.strip().split(maxsplit=1)
    if parts and parts[0].split("@")[0] in ("/help", "/start"):
        return "help", ""
    if len(parts) != 2:
        return None
    mode = parts[0].split("@")[0].lstrip("/").lower()
    try:
        u = urlsplit(parts[1])
        if mode in MODES and u.scheme == "https" and u.hostname in HOSTS and u.port in (None, 443) and not u.username and not u.password:
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

def send(token, chat, text):
    return api(token, "sendMessage", {"chat_id":chat, "text":text[:4000]})

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


def setup(db):
    db.execute("CREATE TABLE IF NOT EXISTS jobs (update_id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, mode TEXT NOT NULL, url TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', error TEXT)")
    db.commit()

def ingest(db, item):
    uid = item["update_id"]
    msg = item.get("message") or {}
    chat = (msg.get("chat") or {}).get("id")
    if chat is None: return
    parsed = parse(msg.get("text", "")) or ("help", "")
    db.execute("INSERT OR IGNORE INTO jobs(update_id,chat,mode,url) VALUES (?,?,?,?)", (uid, chat, *parsed))
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
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(root/"jobs.sqlite") as db:
        setup(db)
        while True:
            job = db.execute("SELECT update_id,chat,mode,url FROM jobs WHERE state='pending' ORDER BY update_id LIMIT 1").fetchone()
            if not job:
                offset = db.execute("SELECT COALESCE(MAX(update_id),0)+1 FROM jobs").fetchone()[0]
                updates = api(token, "getUpdates", {"offset": offset, "timeout": 20, "allowed_updates": '["message"]'})
                for update in updates: ingest(db, update)
            else:
                uid, chat, mode, url = job
                try:
                    if mode == "help":
                        send(token, chat, "/video URL | /audio URL | /subs URL | /transcribe URL")
                    else:
                        send(token, chat, "Job accepted: " + str(uid))
                        folder = root/"downloads"/str(uid)
                        folder.mkdir(parents=True, exist_ok=True)
                        cmd = [args.python, "-m", "ytdlp_tool", mode, url, "--output-dir", str(folder)]
                        if mode == "transcribe": cmd += ["--model", "large-v3", "--model-dir", args.model_dir]
                        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace")
                        if proc.returncode: raise RuntimeError((proc.stderr or "processing failed")[-300:])
                        names = [p for p in folder.rglob("*") if p.is_file()]
                        if mode == "transcribe": names = [p for p in names if p.suffix in (".srt",".txt")]
                        if not names: raise RuntimeError("No output files produced")
                        for path in names[:4]:
                            upload(token, chat, path)
                        send(token, chat, "Completed job " + str(uid))
                    db.execute("UPDATE jobs SET state='done' WHERE update_id=?", (uid,))
                except Exception as exc:
                    db.execute("UPDATE jobs SET state='failed',error=? WHERE update_id=?", (str(exc)[:300],uid))
                    try: send(token, chat, "Job failed. Contact operator.")
                    except Exception: pass
                db.commit()
            if args.once: break

if __name__ == "__main__":
    main()
