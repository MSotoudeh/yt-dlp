"""Final recovery pass after initial serial batch; no overlapping GPU inference."""
import json,os,subprocess,sys,time,zipfile,shutil,importlib.util
from pathlib import Path
ROOT=Path(r"C:\GitHub\yt-dlp")
OUT=Path(r"C:\ProgramData\ytdlp-bot\asr-six-gpu-20261021")
CACHE=ROOT/"output"/"chatgpt"/"asr-six-model-hf"
SOURCE=ROOT/"scripts"/"run-persian-six-gpu-batch.py"
PY=ROOT/"output"/"chatgpt"/"asr-comparison-venv"/"Scripts"/"python.exe"
def status(n):
 p=OUT/(n+".json")
 if not p.exists():return None
 try:return json.loads(p.read_text(encoding="utf-8")).get("status")
 except Exception:return None
def main():
 waited=0
 while True:
  state=OUT/"batch.json"
  if state.is_file():
   try: note=json.loads(state.read_text(encoding="utf-8")).get("batch_note")
   except Exception:note=None
   if note=="completed_all_attempts":break
  if waited>17*3600:raise TimeoutError("First batch incomplete, refusing concurrent GPU job")
  print("WAIT_BATCH",waited,flush=True)
  time.sleep(120)
  waited+=120
 spec=importlib.util.spec_from_file_location("asr_batch",SOURCE)
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 for name in ["gholizadeh","givia"]:
  if status(name)=="complete":continue
  print("RETRY",name,flush=True)
  mod.one(name)
 mod.status("retry_attempts_finished")
 path,included=mod.write_bundle()
 with zipfile.ZipFile(path) as archive:
  corrupt=archive.testzip()
  if corrupt:raise RuntimeError("ZIP corruption in "+corrupt)
 print("ZIP_VERIFIED",path.stat().st_size,"MODEL_TRANSCRIPTS",included,flush=True)
 if any(n in included for n in ["gholizadeh","givia","qwen06","wav2vec"]):
  cmd=[str(PY),str(ROOT/"scripts"/"deliver-persian-six-gpu.py")]
  res=subprocess.run(cmd,cwd=str(ROOT),timeout=240)
  print("DELIVERY_EXIT",res.returncode,flush=True)
 else:print("DELIVERY_SKIPPED_NO_NEW_COMPLETE_MODEL",flush=True)
 # Cache retention is intentional until final artifacts were verified. Do not delete
 # weights without user-visible verification of model output and reliability.
 print("COMPLETE_RETRY_SUPERVISOR",flush=True)
if __name__=="__main__":main()
