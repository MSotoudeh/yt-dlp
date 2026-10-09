"""Evaluate locally stored CTranslate2 Whisper models on RTX 3050 GPU.

CPU inference is never used. Preserve 28-second chunk alignment with the
existing C1Tech Persian comparison and save a status JSON even on failure.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import traceback

def preload_cuda():
    import site
    root=Path(sys.executable).resolve().parents[1]/"Lib"/"site-packages"/"nvidia"
    paths=[]
    handles=[]
    for dll in root.rglob("*.dll"):
        if dll.name.lower().startswith(("cublas","cudnn","cudart")):
            d=str(dll.parent)
            if d not in paths:
                paths.append(d)
                handles.append(os.add_dll_directory(d))
    if not paths:raise RuntimeError("CUDA libraries missing; refuse CPU inference")
    os.environ["PATH"]=os.pathsep.join(paths)+os.pathsep+os.environ["PATH"]
    for name in ("cudart64_12.dll","cublasLt64_12.dll","cublas64_12.dll","cudnn64_9.dll"):
        found=list(root.rglob(name))
        if found:ctypes.WinDLL(str(found[0]))
    return handles

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--label",required=True)
    p.add_argument("--model-path",type=Path,required=True)
    p.add_argument("--audio",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--compute-type",default="int8_float16",choices=["int8_float16","int8"])
    p.add_argument("--beam-size",type=int,default=5)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    key=args.label+"-cuda"
    statusfile=args.output/(key+".json")
    doc=dict(model=args.label,device="cuda",compute_type=args.compute_type,
             beam_size=args.beam_size,status="start",audio_url="https://youtu.be/m8ElotVbO6M")
    def put(s,**kw):
        doc.update(status=s,**kw)
        statusfile.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
        print("STATUS",key,s,flush=True)
    start=time.perf_counter()
    try:
        import numpy as np
        from ytdlp_tool.transcribe import _decode_pcm
        handles=preload_cuda()
        from faster_whisper import WhisperModel
        audio=_decode_pcm(args.audio)
        if audio.ndim!=1:raise ValueError("Expected mono WAV")
        if not (args.model_path/"model.bin").is_file():
            raise FileNotFoundError("Converted CT2 model.bin missing")
        put("loading")
        model=WhisperModel(str(args.model_path),device="cuda",compute_type=args.compute_type,
                           cpu_threads=8,num_workers=1)
        load_s=round(time.perf_counter()-start,2)
        put("inference",load_seconds=load_s)
        segments=[]
        step=16000*28
        total=(len(audio)+step-1)//step
        for i,first in enumerate(range(0,len(audio),step),1):
            chunk=np.asarray(audio[first:first+step],dtype=np.float32)
            iterator,info=model.transcribe(chunk,language="fa",beam_size=args.beam_size,
                      condition_on_previous_text=False,vad_filter=False,task="transcribe")
            words=[s.text.strip() for s in iterator if s.text.strip()]
            text=" ".join(words)
            segments.append(text)
            (args.output/(key+".partial.txt")).write_text("\n".join(segments),encoding="utf-8")
            print("CHUNK",i,"/",total,"CHARACTERS",len(text),flush=True)
        transcript="\n".join(segments)
        if len(transcript.strip())<400:raise ValueError("Transcript empty or abnormally short")
        (args.output/(key+".txt")).write_text(transcript,encoding="utf-8")
        put("complete",seconds=round(time.perf_counter()-start,2),
             characters=len(transcript),chunks=len(segments))
    except BaseException as exc:
        put("failed",seconds=round(time.perf_counter()-start,2),
            error=str(exc)[-750:],traceback=traceback.format_exc()[-2200:])
        raise
if __name__=="__main__":main()
