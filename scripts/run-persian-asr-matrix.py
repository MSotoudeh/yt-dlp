"""Isolated Persian ASR cross-model benchmark. Input is a locally decoded 16kHz WAV.
Usage: python run-persian-asr-matrix.py --model buzz|cv17|c1tech|qwen --device cpu|cuda --audio <wav> --output <dir>
Each run is its own process; error/success JSON retained even if a model fails.
"""
import argparse
import json
import time
import traceback
from pathlib import Path

MODELS = {
 "buzz": "BuzzASR/persian",
 "cv17": "MohammadGholizadeh/whisper-large-v3-persian-common-voice-17",
 "c1tech": "C1Tech/whisper_base_persian",
 "qwen": "Qwen/Qwen3-ASR-1.7B",
}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--model",choices=MODELS,required=True)
 p.add_argument("--device",choices=("cpu","cuda"),required=True)
 p.add_argument("--audio",type=Path,required=True)
 p.add_argument("--chunk-seconds",type=int,default=28,help="Chunk size (default 28 s); can reduce CUDA peak memory")
 p.add_argument("--output",type=Path,required=True)
 args=p.parse_args()
 args.output.mkdir(parents=True,exist_ok=True)
 stem=f"{args.model}-{args.device}"
 checkpoint=args.output/f"{stem}.json"
 log=dict(model=MODELS[args.model],device=args.device,status="starting",chunk_seconds=args.chunk_seconds)
 def status(s,**kw):
  log.update(status=s,**kw)
  checkpoint.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding="utf-8")
  print(f"STATUS {stem} {s}",flush=True)
 t0=time.monotonic()
 status("loading")
 try:
  import torch
  import soundfile as sf
  import numpy as np
  print("TORCH",torch.__version__,"CUDA",torch.cuda.is_available(),flush=True)
  if args.device=="cuda" and not torch.cuda.is_available():
   raise RuntimeError("CUDA unavailable in PyTorch environment")
  wav,sr=sf.read(str(args.audio),dtype="float32")
  if sr!=16000:raise ValueError("Input must be 16kHz")
  if wav.ndim!=1:raise ValueError("Input must be mono")
  if args.model=="qwen":
   from qwen_asr import Qwen3ASRModel
   m=Qwen3ASRModel.from_pretrained(MODELS[args.model],
     dtype=torch.float16 if args.device=="cuda" else torch.float32,
     device_map="cuda:0" if args.device=="cuda" else "cpu",
     max_inference_batch_size=1,max_new_tokens=256)
   loaded=time.monotonic()
   status("inference",load_seconds=round(loaded-t0,2))
   chunks=[]
   for i,start in enumerate(range(0,len(wav),16000*args.chunk_seconds)):
    res=m.transcribe(audio=(np.asarray(wav[start:start+16000*args.chunk_seconds],dtype=np.float32),16000),language="Persian")
    chunks.append(res[0].text)
    (args.output/f"{stem}.partial.txt").write_text("\n".join(chunks),encoding="utf-8")
    print("CHUNK",i+1,"/",(len(wav)+16000*args.chunk_seconds-1)//(16000*args.chunk_seconds),flush=True)
   txt="\n".join(chunks)
  else:
   from transformers import pipeline
   transcriber=pipeline("automatic-speech-recognition",
       model=MODELS[args.model],
       torch_dtype=torch.float16 if args.device=="cuda" else torch.float32,
       device=0 if args.device=="cuda" else -1)
   loaded=time.monotonic()
   status("inference",load_seconds=round(loaded-t0,2))
   chunks=[]
   # Fixed-length 28s sections permit progress and avoid model-specific timestamp issues.
   for i,start in enumerate(range(0,len(wav),16000*args.chunk_seconds)):
    arr=np.asarray(wav[start:start+16000*args.chunk_seconds],dtype=np.float32)
    options={} if args.model=="buzz" else {"task":"transcribe","language":"fa"}
    # BuzzASR has custom vocabulary; forcing Whisper tokenizer language may not work.
    try:
     out=transcriber({"raw":arr,"sampling_rate":sr},generate_kwargs=options)
    except ValueError as e:
     if "language" not in str(e).lower():raise
     out=transcriber({"raw":arr,"sampling_rate":sr})
    chunks.append(out["text"])
    (args.output/f"{stem}.partial.txt").write_text("\n".join(chunks),encoding="utf-8")
    print("CHUNK",i+1,"/",(len(wav)+16000*args.chunk_seconds-1)//(16000*args.chunk_seconds),flush=True)
   txt="\n".join(chunks)
  (args.output/f"{stem}.txt").write_text(txt,encoding="utf-8")
  status("complete",seconds=round(time.monotonic()-t0,2),characters=len(txt),chunks=len(chunks))
 except Exception as e:
  status("failed",seconds=round(time.monotonic()-t0,2),error=str(e)[-800:],traceback=traceback.format_exc()[-2500:])
  raise

if __name__=="__main__":main()
