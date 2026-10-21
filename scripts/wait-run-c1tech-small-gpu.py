"""Wait for the user's *local* Hugging Face token, then run C1Tech Small on GPU.

Never access Brave/browser cookies. Tokens remain in the device-local HF_HOME.
Authentication/permission is a user-side prerequisite, not bypassed.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

REPO=Path(r"C:\GitHub\yt-dlp")
HF_HOME=REPO/"output"/"chatgpt"/"asr-models-hf"
OUT=Path(r"C:\ProgramData\ytdlp-bot\asr-three-gpu-20261009")
OUT.mkdir(parents=True,exist_ok=True)
STATE=OUT/"c1tech-small-watcher.json"
ENV=os.environ.copy()
ENV["HF_HOME"]=str(HF_HOME)
ENV["PYTHONIOENCODING"]="utf-8"
PY=REPO/"output"/"chatgpt"/"asr-comparison-venv"/"Scripts"/"python.exe"
MODEL="C1Tech/whisper_small_persian"

def status(name,**fields):
    record={}
    if STATE.is_file():
        try:record=json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:pass
    record.update(status=name,**fields)
    STATE.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    print("C1TECH_SMALL_WATCHER",name,flush=True)

def main():
    from huggingface_hub import get_token,hf_hub_url
    from huggingface_hub.file_download import get_hf_file_metadata
    begin=time.monotonic()
    end=begin+12*60*60
    status("waiting_for_authorization",model=MODEL,device="cuda:0",timeout_hours=12)
    last_report=0
    while time.monotonic()<end:
        token=get_token()
        if token:
            try:
                meta=get_hf_file_metadata(hf_hub_url(MODEL,"model.safetensors"),token=token,timeout=20)
                if meta.size and meta.size>100_000_000:
                    status("authorization_confirmed",model_size_bytes=meta.size)
                    break
            except Exception as error:
                if time.monotonic()-last_report>1200:
                    status("waiting_for_repository_access",http_status=getattr(getattr(error,"response",None),"status_code",None))
                    last_report=time.monotonic()
        time.sleep(45)
    else:
        status("authorization_timeout")
        return
    result=subprocess.run([str(PY),str(REPO/"scripts"/"benchmark-c1tech-small-gpu.py")],
        env=ENV,cwd=str(REPO),timeout=4*60*60)
    if result.returncode:
        status("gpu_test_failed",exit_code=result.returncode)
        return
    status("gpu_test_complete")
    delivered=subprocess.run([str(PY),str(REPO/"scripts"/"deliver-c1tech-small-gpu.py")],
                             env=ENV,cwd=str(REPO),timeout=240)
    if delivered.returncode:
        status("delivery_failed",exit_code=delivered.returncode)
        return
    status("complete_delivered")
if __name__=="__main__":main()
