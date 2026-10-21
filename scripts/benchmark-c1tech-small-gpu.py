"""Offline RTX 3050 benchmark for a gated C1Tech Small Persian model.

Only downloads the model with an already authorized Hugging Face token and
performs *all inference on cuda:0*. Never changes the production Telegram bot.
"""
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(r"C:\GitHub\yt-dlp")
OUT=Path(r"C:\ProgramData\ytdlp-bot\asr-three-gpu-20261009")
OUT.mkdir(parents=True,exist_ok=True)
STATE=OUT/"c1tech-small-cuda.json"
AUDIO=Path(r"C:\ProgramData\ytdlp-bot\asr-four-models\input-16000.wav")
MODEL="C1Tech/whisper_small_persian"
def note(status,**fields):
    state={}
    if STATE.is_file():
        try:state=json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:pass
    state.update(model=MODEL,device="cuda",status=status,**fields)
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    print("C1TECH_SMALL",status,flush=True)

def main():
    began=time.perf_counter()
    try:
        import torch
        import numpy as np
        import soundfile as sf
        from huggingface_hub import get_token,snapshot_download
        from transformers import pipeline
        if not get_token():
            raise RuntimeError("HF token is missing from this bench environment. Do not try anonymous gated-model access.")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available; CPU inference prohibited by user")
        note("downloading")
        model_path=snapshot_download(repo_id=MODEL,token=get_token(),max_workers=3)
        note("loading",download_seconds=round(time.perf_counter()-began,2))
        speech=pipeline(task="automatic-speech-recognition",model=model_path,
                         device=0,dtype=torch.float16)
        samples,sr=sf.read(str(AUDIO),dtype="float32")
        if sr!=16000 or samples.ndim!=1:raise ValueError("Expected 16k mono WAV")
        note("inference",load_seconds=round(time.perf_counter()-began,2))
        chunk=sr*28
        n=(len(samples)+chunk-1)//chunk
        result=[]
        for index,start in enumerate(range(0,len(samples),chunk),1):
            data=np.asarray(samples[start:start+chunk],dtype=np.float32)
            out=speech({"raw":data,"sampling_rate":sr},
                       generate_kwargs={"language":"fa","task":"transcribe"})
            line=out["text"].strip()
            result.append(line)
            (OUT/"c1tech-small-cuda.partial.txt").write_text("\n".join(result),encoding="utf-8")
            print("CHUNK",index,"/",n,"LEN",len(line),flush=True)
        text="\n".join(result)
        if n!=19 or len(text.strip())<1000:
            raise RuntimeError("Expected complete 19-segment transcript, got blank or truncated output")
        (OUT/"c1tech-small-cuda.txt").write_text(text,encoding="utf-8")
        note("complete",seconds=round(time.perf_counter()-began,2),
             characters=len(text),chunks=len(result),inference_device="cuda:0")
    except Exception as error:
        note("failed",seconds=round(time.perf_counter()-began,2),
             error=str(error)[:600],traceback=traceback.format_exc()[-2200:])
        raise

if __name__=="__main__":main()
