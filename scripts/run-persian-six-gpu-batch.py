"""Sequential and restart-safe GPU-only benchmark batch for the requested ASR models."""
from __future__ import annotations
import json, os, subprocess, sys, time, hashlib, zipfile
from pathlib import Path

ROOT=Path(r"C:\GitHub\yt-dlp")
PY=ROOT/"output"/"chatgpt"/"asr-comparison-venv"/"Scripts"/"python.exe"
ENTRY=ROOT/"scripts"/"benchmark-persian-six-gpu.py"
OUT=Path(r"C:\ProgramData\ytdlp-bot\asr-six-gpu-20261021")
BASE=Path(r"C:\ProgramData\ytdlp-bot\asr-four-models")
OTHER=Path(r"C:\ProgramData\ytdlp-bot\asr-three-gpu-20261009")
OUT.mkdir(parents=True,exist_ok=True)
STATE=OUT/"batch.json"
order=["givia","gholizadeh","qwen06","wav2vec","meta","nvidia"]
model_names={
 "givia":"givia/whisper-large-v3-turbo-persian",
 "gholizadeh":"MohammadGholizadeh/whisper-large-v3-turbo-persian",
 "qwen06":"Qwen/Qwen3-ASR-0.6B",
 "wav2vec":"m3hrdadfi/wav2vec2-large-xlsr-persian-v3",
 "meta":"facebook/omniASR-CTC-300M",
 "nvidia":"nvidia/stt_fa_fastconformer_hybrid_large",
}
def status(note):
 state={}
 for name in order:
  f=OUT/(name+".json")
  if f.exists():
   try: state[name]=json.loads(f.read_text(encoding="utf-8"))
   except Exception as e:state[name]={"status":"corrupt_state","error":str(e)}
 state["batch_note"]=note
 state["input_sha256"]=hashlib.sha256((BASE/"input-16000.wav").read_bytes()).hexdigest()
 state["updated_unix"]=time.time()
 STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
 print("BATCH",note,flush=True)
 return state

def one(name):
 f=OUT/(name+".json")
 if f.exists():
  previous=json.loads(f.read_text(encoding="utf-8"))
  if previous.get("status")=="complete" and (OUT/(name+".txt")).is_file():
   print("SKIP_ALREADY_COMPLETE",name,flush=True)
   return
 if name in ("meta","nvidia") and os.name=="nt":
  detail=("Official fairseq2 dependency does not support native Windows; requires Linux/WSL2 and compatible CUDA binaries" if name=="meta"
          else "Official NVIDIA NeMo ASR framework has no native Windows support; requires Linux/WSL2.")
  f.write_text(json.dumps({"model":model_names[name],"status":"blocked_platform",
      "device":"cuda:0","reason":detail,"inference_performed":False},ensure_ascii=False,indent=2),encoding="utf-8")
  print("BLOCKED_PLATFORM",name,detail,flush=True)
  return
 if __import__("shutil").disk_usage(str(OUT)).free < 7*1024**3:
  raise RuntimeError("Under 7GB free. Abort next model safely without deleting existing results.")
 env=os.environ.copy();env["PYTHONIOENCODING"]="utf-8"
 print("START",name,flush=True)
 try:
  res=subprocess.run([str(PY),str(ENTRY),"--model",name],cwd=str(ROOT),env=env,
    timeout=7200,text=True,encoding="utf-8",errors="replace")
  print("END",name,"exit_code",res.returncode,flush=True)
 except subprocess.TimeoutExpired:
  f.write_text(json.dumps({"model":model_names[name],"status":"timeout","inference_performed":False},indent=2),encoding="utf-8")
  print("TIMEOUT",name,flush=True)
 status("after_"+name)

def write_bundle():
 target=OUT/"Persian-ASR-Six-GPU-Comparison.zip"
 included=[]
 with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED,allowZip64=True) as z:
  base_items=[(BASE,"c1tech-cuda"),(OTHER,"amir-cv17-int8-cuda"),(OTHER,"persian-v4-cuda")]
  new_items=[(OUT,n) for n in order]
  for folder,stem in base_items+new_items:
   p=folder/(stem+".txt")
   s=folder/(stem+".json")
   if s.is_file():z.write(s,"metrics/"+stem+".json")
   if p.is_file() and s.is_file():
    try:valid=json.loads(s.read_text(encoding="utf-8")).get("status")=="complete"
    except Exception:valid=False
    if valid and p.stat().st_size>1000:
     z.write(p,"transcripts/"+stem+".txt")
     included.append(stem)
  if STATE.is_file():z.write(STATE,"metrics/batch.json")
  z.writestr("README.txt",
  "GPU-only Persian ASR benchmark with 19 consecutive 28-second chunks from an 8m50s source (YouTube m8ElotVbO6M).\n"
  "These are raw model outputs. No corrected human ground truth was available; therefore WER/CER and objective accuracy ranking cannot be claimed.\n"
  "Meta Omnilingual and NVIDIA NeMo require Linux/WSL2; native Windows blocked models are marked explicitly.\n"
  "Baseline C1Tech Base, Amir CV17 int8, and Persian v4 included if present.\n"
  "Do not equate character disagreement with error rate.\n")
 print("ARCHIVE",target,"INCLUDED",included,flush=True)
 return target,included

def main():
 start=time.monotonic()
 print("SUPERVISOR_STARTED",flush=True)
 while True:
  f=OUT/"givia.json"
  if f.exists():
   try:phase=json.loads(f.read_text(encoding="utf-8")).get("status")
   except Exception:phase="unknown"
   if phase in ("complete","failed","timeout"):break
  if time.monotonic()-start > 7400:
   print("GIVIA_WAIT_TIMEOUT",flush=True);break
  status("waiting_for_givia")
  time.sleep(30)
 status("givia_finished_or_timed_out")
 for name in order[1:]:one(name)
 status("completed_all_attempts")
 write_bundle()
 print("SUPERVISOR_FINISHED",flush=True)

if __name__=="__main__":main()
