"""Run the published BuzzASR decoding recipe with on-disk checkpoints.

This model uses a replacement tokenizer with built-in language/task prompting,
so specifying Whisper's standard language=fa or task=transcribe can produce
empty output. Run its documented generator settings rather than generic pipeline.
"""
import argparse
import json
import time
import traceback
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--device",choices=["cpu","cuda"],required=True)
    p.add_argument("--audio",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    name=f"buzz-{args.device}-native"
    state=args.output/f"{name}.json"
    report={"model":"BuzzASR/persian","device":args.device,"status":"starting","decoding":"native_prompt_beam1_repeat1.2"}
    def update(status,**d):
        report.update(status=status,**d)
        state.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print("STATUS",name,status,flush=True)
    started=time.monotonic()
    try:
        import soundfile as sf
        import torch
        from transformers import WhisperForConditionalGeneration,WhisperProcessor
        update("loading")
        if args.device=="cuda" and not torch.cuda.is_available():
            raise RuntimeError("PyTorch CUDA unavailable")
        model=WhisperForConditionalGeneration.from_pretrained(
            "BuzzASR/persian",
            torch_dtype=torch.float16 if args.device=="cuda" else torch.float32,
            low_cpu_mem_usage=True,
        ).to(args.device).eval()
        proc=WhisperProcessor.from_pretrained("BuzzASR/persian")
        audio,sr=sf.read(str(args.audio),dtype="float32")
        assert sr==16000 and audio.ndim==1
        load_s=round(time.monotonic()-started,2)
        update("inference",load_seconds=load_s)
        chunks=[]
        count=(len(audio)+16_000*28-1)//(16_000*28)
        for n,start in enumerate(range(0,len(audio),16_000*28),1):
            feats=proc(audio[start:start+16_000*28],sampling_rate=sr,return_tensors="pt").input_features
            feats=feats.to(args.device)
            if args.device=="cuda":
                feats=feats.half()
            with torch.inference_mode():
                ids=model.generate(feats,num_beams=1,no_repeat_ngram_size=3,repetition_penalty=1.2)
            value=proc.batch_decode(ids,skip_special_tokens=True)[0]
            chunks.append(value)
            (args.output/f"{name}.partial.txt").write_text("\n".join(chunks),encoding="utf-8")
            print("CHUNK",n,"/",count,"LENGTH",len(value),flush=True)
        text="\n".join(chunks)
        if not text.strip():
            raise RuntimeError("Empty transcript: decoding did not produce Persian words")
        (args.output/f"{name}.txt").write_text(text,encoding="utf-8")
        update("complete",seconds=round(time.monotonic()-started,2),characters=len(text),chunks=len(chunks))
    except BaseException as e:
        update("failed",seconds=round(time.monotonic()-started,2),error=str(e)[-1000:],traceback=traceback.format_exc()[-3000:])
        raise

if __name__=="__main__":main()
