"""Send verified 2026-10-22 offline ASR review bundle once to the original Telegram chat."""
from pathlib import Path
import json, sqlite3, zipfile
import requests

ROOT=Path(r"C:\ProgramData\ytdlp-bot")
OUT=ROOT/"asr-six-gpu-20261021"
FILE=OUT/"Persian-ASR-GPU-Offline-Human-Review-20261022.zip"
MARKER=OUT/"telegram-review-20261022-delivered.flag"

def main():
 if MARKER.exists():
  print("REVIEW_ALREADY_DELIVERED")
  return
 if not FILE.is_file():raise FileNotFoundError(FILE)
 if FILE.stat().st_size>49_000_000:raise RuntimeError("Too large for bot upload")
 with zipfile.ZipFile(FILE) as z:
  if z.testzip():raise RuntimeError("Corrupt archive")
  names=set(z.namelist())
  required={"index.html","input-16000.wav","transcripts-and-metrics.json",
   "transcripts/c1tech-cuda.txt","transcripts/givia.txt","transcripts/gholizadeh.txt",
   "transcripts/wav2vec.txt","transcripts/qwen06.txt"}
  if not required.issubset(names):raise RuntimeError("Missing verified ASR transcripts/audio")
  info=json.loads(z.read("transcripts-and-metrics.json"))
  if len(info.get("models",{}))!=7:raise RuntimeError("Expected 7 complete transcripts")
  for m in info["models"].values():
   if len(m["segments"])!=19:raise RuntimeError("Partial model transcript")
 with sqlite3.connect(str(ROOT/"state"/"jobs.sqlite")) as db:
  matches=db.execute("select distinct chat from jobs where mode=? and url like ?",("transcribe","%m8ElotVbO6M%")).fetchall()
 if len(matches)!=1:raise RuntimeError("Verified unique Telegram recipient not found")
 token=(ROOT/"telegram-token").read_text(encoding="utf-8").strip()
 with FILE.open("rb") as f:
  response=requests.post("https://api.telegram.org/bot"+token+"/sendDocument",
   data={"chat_id":matches[0][0],"caption":"مقایسه ۷ مدل ASR فارسی با صوت ۸:۵۰، مرورگر آفلاین index.html، پخش ۱۹ قطعه و امکان اصلاح متن و محاسبه WER/CER. برای استفاده ZIP را استخراج کنید."},
   files={"document":(FILE.name,f,"application/zip")},timeout=180)
 if response.status_code!=200 or not response.json().get("ok"):raise RuntimeError("Telegram send failed HTTP "+str(response.status_code))
 MARKER.write_text("delivered",encoding="utf-8")
 print("REVIEW_DELIVERED_TELEGRAM",FILE.name,"BYTES",FILE.stat().st_size)

if __name__=="__main__":main()
