"""Entirely offline inference benchmark for Shenava Koochik (sherpa-onnx).
Model files are locally downloaded once, then inference requires no network.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import traceback

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audio",type=Path,required=True)
    p.add_argument("--model-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    p.add_argument("--threads",type=int,default=8)
    p.add_argument("--chunk-seconds",type=int,default=28)
    a=p.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)
    stem="shenava-koochik-cpu"
    results=a.out_dir/(stem+".json")
    record={"model":"Reza2kn/Shenava-Koochik-v1.0-sherpa-onnx",
            "device":"cpu","engine":"sherpa-onnx","threads":a.threads,
            "chunk_seconds":a.chunk_seconds,"status":"starting"}
    def record_state(status,**kw):
        record.update(status=status,**kw)
        results.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        print("STATUS",stem,status,flush=True)
    start=time.perf_counter()
    try:
        import numpy as np
        import soundfile as sf
        import sherpa_onnx
        record_state("loading")
        model=a.model_dir/"model.onnx"
        tokens=a.model_dir/"tokens.txt"
        for f in [model,tokens]:
            if not f.is_file(): raise FileNotFoundError(str(f))
        rec=sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(model),tokens=str(tokens),num_threads=a.threads)
        load=round(time.perf_counter()-start,2)
        data,sr=sf.read(str(a.audio),dtype="float32")
        if sr!=16000 or data.ndim!=1:raise ValueError("Require mono 16 kHz WAV")
        record_state("inference",model_load_seconds=load)
        texts=[]
        size=sr*a.chunk_seconds
        total=(len(data)+size-1)//size
        for i,s in enumerate(range(0,len(data),size),1):
            stream=rec.create_stream()
            stream.accept_waveform(sr,np.ascontiguousarray(data[s:s+size],dtype=np.float32))
            rec.decode_stream(stream)
            phrase=stream.result.text.strip()
            texts.append(phrase)
            (a.out_dir/(stem+".partial.txt")).write_text("\n".join(texts),encoding="utf-8")
            print("CHUNK",i,"/",total,"CHARACTERS",len(phrase),flush=True)
        text="\n".join(texts)
        if len(text.strip())<500:
            raise RuntimeError("Output too short; likely recognition failure")
        (a.out_dir/(stem+".txt")).write_text(text,encoding="utf-8")
        record_state("complete",seconds=round(time.perf_counter()-start,2),
                    characters=len(text),chunks=len(texts))
    except BaseException as exc:
        record_state("failed",seconds=round(time.perf_counter()-start,2),
                    error=str(exc)[-600:],traceback=traceback.format_exc()[-2000:])
        raise

if __name__=="__main__":main()
