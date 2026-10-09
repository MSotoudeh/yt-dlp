"""Package benchmark transcripts and optionally deliver via the user's existing Telegram bot.

Security: Token and chat destination are read locally. Only the single chat that
requested this exact video transcript qualifies; neither value is printed or
stored in the archive. Never includes audio, token, or unrelated bot jobs.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

MODELS=["c1tech","buzz","cv17","qwen"]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=["preliminary","progress","final"],required=True)
    p.add_argument("--no-send",action="store_true")
    args=p.parse_args()
    root=Path(r"C:\ProgramData\ytdlp-bot")
    data=root/"asr-four-models"
    export=root/"asr-benchmark-delivery"
    export.mkdir(exist_ok=True)
    report=[]
    sources=[]
    for model in MODELS:
        for device in ("cpu","cuda"):
            stem=f"{model}-{device}"
            stems=[stem]
            if model=="buzz":stems=[stem+"-native",stem]
            picked=None
            for choice in stems:
                status=data/(choice+".json")
                trans=data/(choice+".txt")
                if not status.is_file():
                    continue
                item=json.loads(status.read_text(encoding="utf-8"))
                if item.get("status")=="complete" and trans.is_file() and trans.read_text(encoding="utf-8").strip():
                    picked=(choice,trans,item)
                    break
            if picked:
                choice,trans,item=picked
                sources.append((trans,"transcripts/"+choice+".txt"))
                report.append(dict(model=model,device=device,status="valid_output",name=choice,seconds=item.get("seconds"),characters=item.get("characters")))
            else:
                stat=data/(stem+".json")
                if model=="buzz" and (data/(stem+"-native.json")).exists():
                    stat=data/(stem+"-native.json")
                if model=="qwen" and device=="cuda" and (data/"qwen-cuda-smoke-failure.json").exists():
                    stat=data/"qwen-cuda-smoke-failure.json"
                item=json.loads(stat.read_text(encoding="utf-8")) if stat.exists() else {}
                report.append(dict(model=model,device=device,status=item.get("status","not_run"),
                                   reason=(item.get("error","") or "No nonblank validated transcript")[:200]))
    for device in ("cpu","cuda"):
        trans=root/("bench-cpu-full" if device=="cpu" else "bench-gpu-full")/(device+"-transcript.txt")
        if trans.exists():sources.append((trans,"reference-large-v3/"+device+"-transcript.txt"))
    if args.phase=="final":
        if any(v["status"] in ("not_run","starting","loading","inference") for v in report):
            raise RuntimeError("Not all requested model/device attempts have terminal states")
    out=export/("Persian-ASR-comparison-"+args.phase+".zip")
    info=export/("report-"+args.phase+".json")
    info.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    readme=("Transcripts generated from the same source: https://youtu.be/m8ElotVbO6M\n"
            "The original audio is NOT included. Each successful TXT is the raw model output.\n"
            "Blank/failed model runs are listed in status.json; they are not valid transcripts.\n"
            "No model accuracy or WER can be inferred without a human-corrected reference.\n"
            "CPU and CUDA may use different precision; durations include model initialization.\n"
            "A BuzzASR native decoding retry replaces its earlier incorrect empty output.\n"
            "CV17 public model card exists but model weights require Hugging Face access.\n")
    import itertools, difflib, re, csv, io
    words=lambda txt: re.findall(r"[^\\W_]+", txt.casefold(), flags=re.UNICODE)
    by_name={name:words(path.read_text(encoding="utf-8")) for path,name in sources}
    buffer=io.StringIO()
    writer=csv.writer(buffer)
    writer.writerow(["source_a","source_b","word_agreement_percent","tokens_a","tokens_b"])
    for (name_a,tokens_a),(name_b,tokens_b) in itertools.combinations(by_name.items(),2):
        similarity=difflib.SequenceMatcher(a=tokens_a,b=tokens_b,autojunk=False).ratio()
        writer.writerow([name_a,name_b,round(similarity*100,2),len(tokens_a),len(tokens_b)])
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        z.writestr("README.txt",readme)
        z.write(info,"status.json")
        z.writestr("word_agreement.csv",buffer.getvalue())
        for src,arc in sources:z.write(src,arc)
    print("PACKAGE_READY",out.name,"BYTES",out.stat().st_size,"SUCCESSFUL",len([x for x in report if x["status"]=="valid_output"]),flush=True)
    if args.no_send:return
    marker=export/("delivered-"+args.phase+".flag")
    if marker.exists():
        print("ALREADY_DELIVERED",args.phase)
        return
    matches=[]
    with sqlite3.connect(str(root/"state"/"jobs.sqlite")) as db:
        matches=db.execute("select distinct chat from jobs where mode=? and url like ?",("transcribe","%m8ElotVbO6M%")).fetchall()
    if len(matches)!=1:raise RuntimeError("Recipient not uniquely established from prior /transcribe job")
    token=(root/"telegram-token").read_text(encoding="utf-8").strip()
    if not token:raise RuntimeError("Bot token unreadable")
    import requests
    api="https://api.telegram.org/bot"+token+"/sendDocument"
    cap="خروجی مقایسه مدل‌های تشخیص گفتار فارسی (نسخه "+("نهایی" if args.phase=="final" else "اولیه")+"). فایل ZIP شامل متن‌های کامل معتبر و وضعیت آزمون‌هاست."
    with out.open("rb") as f:
        try:
            resp=requests.post(api,data={"chat_id":matches[0][0],"caption":cap},
                    files={"document":(out.name,f,"application/zip")},timeout=120)
        except requests.RequestException:
            raise RuntimeError("Telegram upload request failed (details suppressed)")
    if resp.status_code!=200:
        raise RuntimeError("Telegram document upload HTTP status "+str(resp.status_code))
    if not resp.json().get("ok"):raise RuntimeError("Telegram declined document")
    marker.write_text("delivered",encoding="utf-8")
    print("TELEGRAM_DELIVERED",args.phase,"file_size",out.stat().st_size)

if __name__=="__main__":main()
