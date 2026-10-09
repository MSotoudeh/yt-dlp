"""Durable, local-only GPU ASR trials for 2026-10-09.

Never infer on CPU. Exact two publicly available candidate repos are tested
one at a time. C1Tech Small remains blocked unless its owner grants access.
After each evaluation, remove ONLY the new non-C1Tech weight cache.
Preserve generated transcripts, metrics, source WAV and production weights.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
import zipfile

REPO=Path(r"C:\GitHub\yt-dlp")
HUB=REPO/"output"/"chatgpt"/"asr-models-hf"/"hub"
CMP_PY=REPO/"output"/"chatgpt"/"asr-comparison-venv"/"Scripts"/"python.exe"
ASR_PY=REPO/"output"/"chatgpt"/"asr-venv"/"Scripts"/"python.exe"
ROOT=Path(r"C:\ProgramData\ytdlp-bot")
OUTPUT=ROOT/"asr-three-gpu-20261009"
OUTPUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/"asr-four-models"/"input-16000.wav"
ENV=os.environ.copy()
ENV["HF_HOME"]=str(HUB.parent)
ENV["HF_HUB_CACHE"]=str(HUB)
ENV["HF_XET_CACHE"]=str(OUTPUT/"xet-temp")
ENV["PYTHONIOENCODING"]="utf-8"
ENV["HF_HUB_DISABLE_PROGRESS_BARS"]="1"
AMIR_REPO="AmirMohseni/whisper-large-v3-persian-ct2-int8"
V4_REPO="nezamisafa/whisper-persian-v4"
REPO_CACHES={
 "amir":HUB/"models--AmirMohseni--whisper-large-v3-persian-ct2-int8",
 "v4":HUB/"models--nezamisafa--whisper-persian-v4",
}
MODEL_PATH=OUTPUT/"v4-converted-ct2"
BASELINE=ROOT/"asr-four-models"/"c1tech-cuda.txt"
def say(*msg): print(*msg,flush=True)
def free():return shutil.disk_usage("C:\\").free
def record(key,state,**details):
    f=OUTPUT/(key+".json")
    prev={}
    if f.exists():
        try: prev=json.loads(f.read_text(encoding="utf-8"))
        except: pass
    prev.update(status=state,**details)
    f.write_text(json.dumps(prev,ensure_ascii=False,indent=2),encoding="utf-8")
    say("STATE",key,state)
def run(command,label,timeout=21600):
    say("RUN",label,"START",time.strftime("%Y-%m-%dT%H:%M:%S"))
    proc=subprocess.run(list(map(str,command)),env=ENV,cwd=str(REPO),timeout=timeout)
    say("RUN",label,"EXIT",proc.returncode)
    if proc.returncode:
        raise RuntimeError(label+" process failed (exit "+str(proc.returncode)+")")
def remove_weight_dir(path):
    if not path.exists():return
    path=path.resolve()
    # Refuse to remove any directory outside this exact scratch model set.
    safe=[p.resolve() for p in [*REPO_CACHES.values(),MODEL_PATH,OUTPUT/"xet-temp"]]
    if path not in safe:raise ValueError("Unexpected cleanup path")
    say("CLEANUP_MODEL",path)
    shutil.rmtree(path)
def hf_download(repo_id,allow):
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(repo_id=repo_id,allow_patterns=allow,max_workers=2))
def benchmark(label,model_path,compute="int8_float16"):
    run([ASR_PY,REPO/"scripts"/"benchmark-new-persian-ct2-gpu.py",
         "--label",label,"--model-path",model_path,
         "--audio",SRC,"--output",OUTPUT,
         "--compute-type",compute],"gpu-"+label,timeout=10000)
def trial_amir():
    key="amir-cv17-int8"
    if (OUTPUT/(key+"-cuda.json")).exists():
        try:
            d=json.loads((OUTPUT/(key+"-cuda.json")).read_text(encoding="utf-8"))
            if d.get("status")=="complete" and (OUTPUT/(key+"-cuda.txt")).exists():
                say("SKIP_COMPLETED",key);return
        except:pass
    record(key,"downloading",repo_id=AMIR_REPO,device="cuda")
    t=time.perf_counter()
    try:
        snapshot=hf_download(AMIR_REPO,
            ["model.bin","config.json","tokenizer.json","vocabulary.json",
             "preprocessor_config.json","tokenizer_config.json","generation_config.json"])
        record(key,"downloaded",download_seconds=round(time.perf_counter()-t,2))
        benchmark(key,snapshot)
        record(key,"complete",wall_seconds=round(time.perf_counter()-t,2))
    except BaseException as e:
        record(key,"failed",reason=str(e)[:450])
        say("TRIAL_FAILED",key,type(e).__name__)
    finally:
        try:remove_weight_dir(REPO_CACHES["amir"])
        except Exception as e:say("CLEANUP_FAILED",key,str(e)[:200])
def trial_v4():
    key="persian-v4"
    if (OUTPUT/(key+"-cuda.json")).exists():
        try:
            d=json.loads((OUTPUT/(key+"-cuda.json")).read_text(encoding="utf-8"))
            if d.get("status")=="complete" and (OUTPUT/(key+"-cuda.txt")).exists():
                say("SKIP_COMPLETED",key);return
        except:pass
    record(key,"downloading",repo_id=V4_REPO,device="cuda")
    t=time.perf_counter()
    try:
        snapshot=hf_download(V4_REPO,
            ["*.safetensors","*.json","merges.txt","vocab.json","*.model"])
        record(key,"downloaded",download_seconds=round(time.perf_counter()-t,2),
               free_bytes=free())
        from transformers import AutoTokenizer
        # This repository lacks tokenizer.json; generate it locally from
        # vocab.json/merges.txt so faster-whisper can open the converted model.
        if not(snapshot/"tokenizer.json").exists():
            tok=AutoTokenizer.from_pretrained(str(snapshot),use_fast=True)
            tok.save_pretrained(str(snapshot))
            say("CREATED_LOCAL_TOKENIZER_JSON")
        record(key,"converting")
        cmd=CMP_PY.parent/"ct2-transformers-converter.exe"
        if not cmd.exists():raise RuntimeError("Missing ct2-transformers-converter.exe")
        run([cmd,"--model",snapshot,"--output_dir",MODEL_PATH,
             "--quantization","int8_float16","--copy_files",
             "tokenizer.json","preprocessor_config.json"],
            "convert-v4-to-ct2-int8-float16",timeout=10000)
        if not(MODEL_PATH/"model.bin").is_file():
            raise RuntimeError("V4 conversion did not create model.bin")
        record(key,"converted",ct2_bytes=(MODEL_PATH/"model.bin").stat().st_size)
        benchmark(key,MODEL_PATH)
        record(key,"complete",wall_seconds=round(time.perf_counter()-t,2))
    except BaseException as e:
        record(key,"failed",reason=str(e)[:450])
        say("TRIAL_FAILED",key,type(e).__name__)
    finally:
        for path in [REPO_CACHES["v4"],MODEL_PATH]:
            try:remove_weight_dir(path)
            except Exception as e:say("CLEANUP_FAILED",str(path),str(e)[:220])
def bundle_and_deliver():
    export=ROOT/"asr-benchmark-delivery"
    export.mkdir(exist_ok=True)
    filename=export/"Persian-ASR-next-three-GPU-comparison.zip"
    files=[]
    for key in ["amir-cv17-int8","persian-v4"]:
        for suffix in [".json","-cuda.json","-cuda.txt"]:
            p=OUTPUT/(key+suffix)
            if p.exists():files.append((p,p.name))
    if BASELINE.exists():files.append((BASELINE,"C1Tech-Base-GPU-reference.txt"))
    base_json=ROOT/"asr-four-models"/"c1tech-cuda.json"
    if base_json.exists():files.append((base_json,"C1Tech-Base-GPU-reference.json"))
    gated={"model":"C1Tech/whisper_small_persian","status":"blocked",
           "reason":"Manual gated license and authentication required; no weights downloaded"}
    summary={
      "models_tested_gpu":["AmirMohseni/whisper-large-v3-persian-ct2-int8",
                           "nezamisafa/whisper-persian-v4"],
      "c1tech_small":gated,
      "baseline":"C1Tech Whisper Base Persian (prior GPU output)",
      "input":"https://youtu.be/m8ElotVbO6M",
      "no_cloud_asr":True,
      "note":"Accuracy requires subjective inspection or human-corrected WER; speed is wall-clock including download for wrapper and load/inference for GPU script.",
      "free_bytes_after_clean":free()}
    with zipfile.ZipFile(filename,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("summary.json",json.dumps(summary,ensure_ascii=False,indent=2))
        for p,name in files:z.write(p,name)
    say("FINAL_ZIP_READY",filename.name,"BYTES",filename.stat().st_size)
    marker=export/"delivered-next-three-gpu.flag"
    if marker.exists():say("PREVIOUSLY_DELIVERED");return
    matches=[]
    try:
        with sqlite3.connect(str(ROOT/"state"/"jobs.sqlite")) as db:
            matches=db.execute("select distinct chat from jobs where mode=? and url like ?",
                   ("transcribe","%m8ElotVbO6M%")).fetchall()
        if len(matches)!=1:raise RuntimeError("Recipient not unique")
        import requests
        token=(ROOT/"telegram-token").read_text(encoding="utf-8").strip()
        with filename.open("rb") as f:
            resp=requests.post("https://api.telegram.org/bot"+token+"/sendDocument",
                data={"chat_id":matches[0][0],
                      "caption":"خروجی آزمایش GPU مدل‌های فارسی جدید و مقایسه با C1Tech Base. شامل متن‌ها، زمان‌ها و وضعیت دسترسی C1Tech Small؛ بدون API تشخیص گفتار."},
                files={"document":(filename.name,f,"application/zip")},timeout=120)
        if resp.status_code!=200 or not resp.json().get("ok"):
            raise RuntimeError("Telegram delivery HTTP status "+str(resp.status_code))
        marker.write_text("delivered",encoding="utf-8")
        say("DELIVERED_PRIVATE_TELEGRAM_OK")
    except Exception as e:
        say("DELIVERY_PENDING",type(e).__name__,str(e)[:140])
def main():
    if not SRC.is_file():raise FileNotFoundError("Missing source WAV")
    if not BASELINE.is_file():raise FileNotFoundError("Missing previous C1Tech Base transcript")
    if not (HUB/"models--C1Tech--whisper_base_persian").is_dir():
        raise RuntimeError("C1Tech protected model unavailable")
    say("FREE_START",free())
    record("c1tech-small","blocked",repo_id="C1Tech/whisper_small_persian",
           reason="GatedRepoError HTTP 401, no authorized HF account; owner approval required",
           device="cuda",download_attempted=False)
    trial_amir()
    trial_v4()
    try:remove_weight_dir(OUTPUT/"xet-temp")
    except Exception as e:say("XET_CLEANUP_FAILED",str(e)[:200])
    say("FREE_END",free())
    bundle_and_deliver()
    say("TRIALS_FINISHED")
if __name__=="__main__":main()
