"""Reproducible Persian ASR GPU-only trials on Ops; no production bot mutations."""
from __future__ import annotations
import argparse, gc, json, math, os, subprocess, sys, time, traceback
from pathlib import Path

ROOT=Path(r"C:\GitHub\yt-dlp")
AUDIO=Path(r"C:\ProgramData\ytdlp-bot\asr-four-models\input-16000.wav")
OUT=Path(r"C:\ProgramData\ytdlp-bot\asr-six-gpu-20261021")
HF_CACHE=ROOT/"output"/"chatgpt"/"asr-six-model-hf"
OUT.mkdir(parents=True,exist_ok=True)
HF_CACHE.mkdir(parents=True,exist_ok=True)
os.environ["HF_HOME"]=str(HF_CACHE)
os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
os.environ["PYTHONIOENCODING"]="utf-8"
MODELS={
 "givia":"givia/whisper-large-v3-turbo-persian",
 "gholizadeh":"MohammadGholizadeh/whisper-large-v3-turbo-persian",
 "qwen06":"Qwen/Qwen3-ASR-0.6B",
 "wav2vec":"m3hrdadfi/wav2vec2-large-xlsr-persian-v3",
 "meta":"facebook/omniASR-CTC-300M",
 "nvidia":"nvidia/stt_fa_fastconformer_hybrid_large",
}
def report(name,status,**kw):
 p=OUT/(name+".json")
 data={}
 if p.exists():
  try:data=json.loads(p.read_text(encoding="utf-8"))
  except Exception:pass
 data.update(model=MODELS[name],device="cuda:0",status=status,**kw)
 if status=="complete":
  data.pop("error",None)
  data.pop("traceback",None)
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
 print("MODEL",name,status,flush=True)

def verify_cuda():
 import torch
 if not torch.cuda.is_available():raise RuntimeError("CUDA unavailable: CPU-only forbidden")
 return torch

def audio_chunks():
 import soundfile as sf,numpy as np
 a,sr=sf.read(str(AUDIO),dtype="float32")
 if sr!=16000 or a.ndim!=1:raise ValueError("Expected mono 16k audio")
 chunks=[np.asarray(a[i:i+sr*28],dtype=np.float32) for i in range(0,len(a),sr*28)]
 if len(chunks)!=19:raise ValueError("Expected 19 x 28-sec chunks, got "+str(len(chunks)))
 return chunks,sr

def run_whisper_hf(name,chunks,sr):
 import torch
 from transformers import AutoProcessor,AutoModelForSpeechSeq2Seq
 repo=MODELS[name]
 report(name,"downloading_or_loading")
 proc=AutoProcessor.from_pretrained("openai/whisper-large-v3-turbo",cache_dir=str(HF_CACHE),use_fast=True)
 model=AutoModelForSpeechSeq2Seq.from_pretrained(repo,cache_dir=str(HF_CACHE),torch_dtype=torch.float16,low_cpu_mem_usage=True,use_safetensors=True).to("cuda:0").eval()
 if next(model.parameters()).device.type!="cuda":raise RuntimeError("Model not on CUDA")
 lines=[]
 report(name,"inference",gpu_memory_mb=round(torch.cuda.memory_allocated()/2**20))
 for i,part in enumerate(chunks,1):
  inp=proc(part,sampling_rate=sr,return_tensors="pt").input_features.to("cuda:0",dtype=torch.float16)
  with torch.inference_mode():
   out=model.generate(inp,language="persian",task="transcribe",max_new_tokens=256,num_beams=1)
  text=proc.batch_decode(out,skip_special_tokens=True)[0].strip()
  lines.append(text)
  (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
  print(name,"CHUNK",i,"/",len(chunks),"chars",len(text),flush=True)
 del model
 torch.cuda.empty_cache()
 return lines

def run_wav2vec(name,chunks,sr):
 import torch
 from transformers import AutoProcessor,AutoModelForCTC
 repo=MODELS[name];report(name,"downloading_or_loading")
 proc=AutoProcessor.from_pretrained(repo,cache_dir=str(HF_CACHE))
 model=AutoModelForCTC.from_pretrained(repo,cache_dir=str(HF_CACHE),use_safetensors=False).to("cuda:0").eval()
 if next(model.parameters()).device.type!="cuda":raise RuntimeError("Model not on CUDA")
 report(name,"inference",gpu_memory_mb=round(torch.cuda.memory_allocated()/2**20))
 lines=[]
 for i,part in enumerate(chunks,1):
  inputs=proc(part,sampling_rate=sr,return_tensors="pt",padding=True)
  features=inputs.input_values.to("cuda:0")
  with torch.inference_mode(): logits=model(input_values=features).logits
  trans=proc.batch_decode(logits.argmax(dim=-1))[0].strip()
  lines.append(trans)
  (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
  print(name,"CHUNK",i,"/",len(chunks),"chars",len(trans),flush=True)
 del model
 torch.cuda.empty_cache()
 return lines

def run_qwen(name,chunks,sr):
 import torch
 from qwen_asr import Qwen3ASRModel
 report(name,"downloading_or_loading")
 model=Qwen3ASRModel.from_pretrained(MODELS[name],dtype=torch.float16,device_map="cuda:0",max_inference_batch_size=1,max_new_tokens=512,cache_dir=str(HF_CACHE))
 report(name,"inference",gpu_memory_mb=round(torch.cuda.memory_allocated()/2**20))
 if not torch.cuda.memory_allocated():raise RuntimeError("CUDA memory not allocated: GPU-only check failed")
 lines=[]
 for i,part in enumerate(chunks,1):
  answer=model.transcribe(audio=(part,sr),language="Persian")
  trans=answer[0].text.strip()
  lines.append(trans)
  (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
  print(name,"CHUNK",i,"/",len(chunks),"chars",len(trans),flush=True)
 del model
 torch.cuda.empty_cache()
 return lines

def run_givia(name,chunks,sr):
 import soundfile as sf
 from huggingface_hub import hf_hub_download
 exe=ROOT/"output"/"chatgpt"/"whisper-large-benchmark-20261020"/"whisper-cuda"/"Release"/"whisper-cli.exe"
 if not exe.exists():raise FileNotFoundError("CUDA whisper-cli missing")
 report(name,"downloading")
 model=hf_hub_download(MODELS[name],filename="ggml-persian-v3-turbo.bin",cache_dir=str(HF_CACHE))
 report(name,"inference")
 partial=OUT/(name+".partial.txt")
 lines=[]
 if partial.is_file():
  old=partial.read_text(encoding="utf-8").splitlines()
  if 1<=len(old)<len(chunks) and all(len(x.strip())>=40 for x in old):
   lines=old
   print("GIVIA_RESUMING_VALIDATED_CHUNKS",len(lines),flush=True)
 resumed_from=len(lines)
 for i,part in enumerate(chunks,1):
  if i<=len(lines):continue
  wav=OUT/("givia-segment-%02d.wav"%i)
  sf.write(str(wav),part,sr,subtype="PCM_16")
  pref=OUT/("givia-segment-%02d-output"%i)
  try:
   cmd=[str(exe),"-m",str(model),"-f",str(wav),"-l","fa","-nt","-otxt","-of",str(pref),"-t","4","-bs","1","-bo","1"]
   result=subprocess.run(cmd,capture_output=True,text=True,errors="replace",timeout=600)
   diag=result.stderr+"\n"+result.stdout
   if result.returncode:raise RuntimeError("whisper-cli failed: "+diag[-1400:])
   if i==1:
    (OUT/"givia-cuda-log-excerpt.txt").write_text(diag[-3500:],encoding="utf-8")
    if not any(v in diag.lower() for v in ("cuda","gpu")):
     raise RuntimeError("CUDA not evidenced in whisper-cli logs; reject CPU fallback")
   raw=pref.with_suffix(".txt").read_bytes()
   text=raw.decode("utf-8-sig",errors="replace").strip()
   bad=text.count("\ufffd")
   if bad:
    (OUT/("givia-segment-%02d-raw.bin"%i)).write_bytes(raw)
    with (OUT/"givia-encoding-warnings.jsonl").open("a",encoding="utf-8") as warn:
     warn.write(json.dumps({"segment":i,"replacement_characters":bad,"original_bytes_preserved":True})+"\n")
    print("GIVIA_MALFORMED_UTF8_BYTES",i,"replacement_chars",bad,flush=True)
   if bad>8:raise RuntimeError("Too many malformed UTF-8 bytes in segment "+str(i))
   lines.append(text)
   (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
   print(name,"CHUNK",i,"/",len(chunks),"chars",len(text),flush=True)
  finally:
   wav.unlink(missing_ok=True)
   pref.with_suffix(".txt").unlink(missing_ok=True)
 return lines,resumed_from

def run_meta(name,chunks,sr):
 try:from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
 except (ImportError, OSError) as ex:raise RuntimeError("Meta fairseq2/omnilingual-asr native Windows dependency unavailable: "+str(ex)) from ex
 import torch,soundfile as sf
 pipeline=ASRInferencePipeline(model_card="omniASR_CTC_300M",device="cuda:0")
 lines=[]
 for i,part in enumerate(chunks,1):
  wav=OUT/("meta-chunk-%02d.wav"%i);sf.write(str(wav),part,sr,subtype="PCM_16")
  try:
   text=pipeline.transcribe([str(wav)],batch_size=1)[0].strip()
   lines.append(text)
   (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
  finally:wav.unlink(missing_ok=True)
  print(name,"CHUNK",i,"/",len(chunks),"chars",len(text),flush=True)
 return lines

def run_nvidia(name,chunks,sr):
 try:import nemo.collections.asr as nemo_asr
 except (ImportError,OSError) as ex:raise RuntimeError("NVIDIA NeMo Windows inference dependency unavailable: "+str(ex)) from ex
 import torch,soundfile as sf
 model=nemo_asr.models.ASRModel.from_pretrained(MODELS[name]).to("cuda:0")
 if next(model.parameters()).device.type!="cuda":raise RuntimeError("NVIDIA model not on CUDA")
 lines=[]
 for i,part in enumerate(chunks,1):
  wav=OUT/("nvidia-chunk-%02d.wav"%i);sf.write(str(wav),part,sr,subtype="PCM_16")
  try:
   trans=model.transcribe([str(wav)])[0]
   text=(trans.text if hasattr(trans,"text") else str(trans)).strip()
   lines.append(text)
   (OUT/(name+".partial.txt")).write_text("\n".join(lines),encoding="utf-8")
  finally:wav.unlink(missing_ok=True)
  print(name,"CHUNK",i,"/",len(chunks),"chars",len(text),flush=True)
 return lines

def main(name):
 began=time.perf_counter()
 try:
  torch=verify_cuda()
  chunks,sr=audio_chunks()
  report(name,"starting",chunks_expected=len(chunks),gpu=torch.cuda.get_device_name(0),gpu_total_memory_mb=round(torch.cuda.get_device_properties(0).total_memory/2**20))
  extra_metrics={}
  if name=="givia":
   lines,resumed_from=run_givia(name,chunks,sr)
   extra_metrics={"timing_scope":"resumed_run_only" if resumed_from else "full_run",
      "resumed_existing_chunks":resumed_from,"timed_chunks":len(lines)-resumed_from}
  elif name=="gholizadeh":lines=run_whisper_hf(name,chunks,sr)
  elif name=="wav2vec":lines=run_wav2vec(name,chunks,sr)
  elif name=="qwen06":lines=run_qwen(name,chunks,sr)
  elif name=="meta":lines=run_meta(name,chunks,sr)
  else:lines=run_nvidia(name,chunks,sr)
  content="\n".join(lines)
  if len(lines)!=19 or len(content)<1000:raise RuntimeError("Missing chunks or suspiciously empty transcript")
  (OUT/(name+".txt")).write_text(content,encoding="utf-8")
  report(name,"complete",seconds=round(time.perf_counter()-began,2),characters=len(content),chunks=len(lines),gpu_only=True,**extra_metrics)
 except Exception as ex:
  report(name,"failed",seconds=round(time.perf_counter()-began,2),error=str(ex)[:900],traceback=traceback.format_exc()[-1800:])
  raise

if __name__=="__main__":
 ap=argparse.ArgumentParser()
 ap.add_argument("--model",choices=MODELS,required=True)
 args=ap.parse_args()
 main(args.model)
