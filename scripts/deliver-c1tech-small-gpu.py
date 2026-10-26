"""Private distribution of completed, fully local GPU Persian ASR trials."""
import json
from pathlib import Path
import sqlite3
import zipfile

def main():
    root=Path(r"C:\ProgramData\ytdlp-bot")
    output=root/"asr-three-gpu-20261009"
    out=root/"asr-benchmark-delivery"
    out.mkdir(parents=True,exist_ok=True)
    target=out/"Persian-ASR-C1Tech-Small-GPU-Comparison.zip"
    models=[
        (root/"asr-four-models","c1tech-cuda"),
        (output,"amir-cv17-int8-cuda"),
        (output,"persian-v4-cuda"),
        (output,"c1tech-small-cuda"),
    ]
    complete=[]
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as archive:
        for folder,stem in models:
            transcript=folder/(stem+".txt")
            state_file=folder/(stem+".json")
            if not(transcript.is_file() and state_file.is_file()):
                continue
            state=json.loads(state_file.read_text(encoding="utf-8"))
            if state.get("status")!="complete" or not transcript.read_text(encoding="utf-8").strip():
                continue
            archive.write(transcript,"transcripts/"+stem+".txt")
            archive.write(state_file,"metrics/"+stem+".json")
            complete.append(stem)
        archive.writestr("README.txt","Offline GPU-only model evaluations on https://youtu.be/m8ElotVbO6M. Raw transcripts, not ground truth. No remote ASR API used. Compare against user-corrected audio before accepting any model. ")
    if "c1tech-small-cuda" not in complete:raise RuntimeError("Refuse to send an incomplete C1Tech Small trial")
    print("ARCHIVE_READY",target.name,target.stat().st_size,complete,flush=True)
    marker=out/"delivered-c1tech-small-gpu.flag"
    if marker.exists():print("ALREADY_DELIVERED");return
    import requests
    with sqlite3.connect(str(root/"state"/"jobs.sqlite")) as db:
        matches=db.execute("select distinct chat from jobs where mode=? and url like ?",("transcribe","%m8ElotVbO6M%")).fetchall()
    if len(matches)!=1:raise RuntimeError("Verified Telegram recipient unavailable")
    token=(root/"telegram-token").read_text(encoding="utf-8").strip()
    with target.open("rb") as f:
        reply=requests.post("https://api.telegram.org/bot"+token+"/sendDocument",
          data={"chat_id":matches[0][0],
                "caption":"خروجی GPU مدل C1Tech Small و مقایسه با Base، CV17 INT8 و Persian v4؛ بدون سرویس تشخیص گفتار ابری."},
          files={"document":(target.name,f,"application/zip")},timeout=120)
    if reply.status_code!=200 or not reply.json().get("ok"):
        raise RuntimeError("Telegram delivery failed with HTTP "+str(reply.status_code))
    marker.write_text("delivered",encoding="utf-8")
    print("DELIVERED",target.name,target.stat().st_size,flush=True)

if __name__=="__main__":main()
