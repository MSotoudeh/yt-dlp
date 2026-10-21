"""Deliver verified benchmark archive privately, without revealing Telegram credentials."""
from pathlib import Path
import requests,sqlite3,zipfile
ROOT=Path(r"C:\ProgramData\ytdlp-bot")
OUT=ROOT/"asr-six-gpu-20261021"
FILE=OUT/"Persian-ASR-Six-GPU-Comparison.zip"
MARKER=OUT/"telegram-delivered.flag"
def main():
 if MARKER.exists():print("ALREADY_DELIVERED");return
 if not FILE.is_file():raise FileNotFoundError("Archive missing")
 with zipfile.ZipFile(FILE) as z:
  if z.testzip():raise RuntimeError("Archive integrity test failed")
  text=[v for v in z.namelist() if v.startswith("transcripts/")]
  if not any(v.endswith(("givia.txt","gholizadeh.txt","qwen06.txt","wav2vec.txt")) for v in text):
   raise RuntimeError("No new complete experiment; refusing to send baseline-only archive")
 with sqlite3.connect(str(ROOT/"state"/"jobs.sqlite")) as db:
  matches=db.execute("select distinct chat from jobs where mode=? and url like ?",("transcribe","%m8ElotVbO6M%")).fetchall()
 if len(matches)!=1:raise RuntimeError("Ambiguous or missing verified recipient")
 secret=(ROOT/"telegram-token").read_text(encoding="utf-8").strip()
 with FILE.open("rb") as f:
  response=requests.post("https://api.telegram.org/bot"+secret+"/sendDocument",
   data={"chat_id":matches[0][0],"caption":"مقایسه ASR فارسی روی GPU لپ‌تاپ: خروجی‌ها و لاگ مدل‌های قابل‌اجرا؛ نتایج نیازمند Ground Truth برای سنجش WER هستند."},
   files={"document":(FILE.name,f,"application/zip")},timeout=120)
 if response.status_code!=200 or not response.json().get("ok"):
  raise RuntimeError("Telegram file delivery failed; HTTP "+str(response.status_code))
 MARKER.write_text("sent",encoding="utf-8")
 print("DELIVERED_PRIVATE_TELEGRAM",FILE.name,FILE.stat().st_size)
if __name__=="__main__":main()
