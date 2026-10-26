"""Generate a reproducible summary of the 4-model Persian ASR comparison.

No raw transcript or account credentials are committed to Git.
"""
from pathlib import Path
import json
import datetime

root=Path(r"C:\ProgramData\ytdlp-bot\asr-four-models")
dest=Path(r"C:\GitHub\yt-dlp\docs\persian-asr-four-models-2026-10-09.md")
models=[
 ("C1Tech Whisper Base Persian","c1tech"),
 ("BuzzASR Persian","buzz"),
 ("Whisper Large-v3 Persian CV17","cv17"),
 ("Qwen3-ASR 1.7B","qwen"),
]
lines=[
 "# Persian ASR four-model evaluation — 2026-10-09",
 "",
 "## Method",
 "",
 "- Input: https://youtu.be/m8ElotVbO6M (~8:50), same locally decoded 16 kHz mono WAV.",
 "- Source text judged by the user; this experiment does not have a gold-reference WER or CER.",
 "- Four candidate checkpoints, each tested independently on CPU and (if possible) RTX 3050 4 GiB CUDA GPU.",
 "- Both paths use 28-second non-overlapping chunks, except short hardware smoke tests.",
 "- CPU uses float32 and GPU float16 where supported. Numerical differences may affect transcription.",
 "- Model instructions, access policy and memory capacity may preclude a valid transcript.",
 "- BuzzASR requires its native generation prompt; a generic forced-language run produced empty output and is INVALID.",
 "",
 "## Benchmark",
 "",
 "| Model | Device | Result | Wall time | Characters | Notes |",
 "|---|---|---|---:|---:|---|",
]
for human,model in models:
    for device in ("cpu","cuda"):
        names=[f"{model}-{device}"]
        if model=="buzz":
            names=[f"{model}-{device}-native",f"{model}-{device}"]
        status="not_run"; seconds=None; chars=None; note=""
        for name in names:
            js=root/(name+".json")
            if not js.exists():continue
            d=json.loads(js.read_text(encoding="utf-8"))
            source=root/(name+".txt")
            status=d.get("status","unknown")
            seconds=d.get("seconds")
            chars=d.get("characters")
            note=(d.get("error","") or "")[:140].replace("|","/").replace(chr(13)," ").replace(chr(10)," ")
            if status=="complete" and source.exists() and source.read_text(encoding="utf-8").strip():
                status="valid_txt"
                break
            if status=="complete":status="invalid_empty"
        if model=="qwen" and device=="cuda" and status!="valid_txt":
            t=root/"qwen-cuda-smoke-failure.json"
            if t.exists():
                err=json.loads(t.read_text(encoding="utf-8"))
                status="failed_smoke"
                note=(err.get("error") or "GPU smoke failed")[:140].replace("|","/")
        pretty="—" if seconds is None else f"{seconds/60:.2f} min"
        count="—" if chars is None else str(chars)
        lines.append(f"| {human} | {device.upper()} | {status} | {pretty} | {count} | {note} |")
lines+=["","## Delivery and limitations","",
 "- Valid TXT outputs and a per-run status report are placed in a private ZIP bundle and sent only to the previously verified Telegram chat that submitted this video's /transcribe request.",
 "- These transcript texts are **not** committed to a public repository.",
 "- CV17 model weights currently require gated Hugging Face authorization; its public model card alone is insufficient.",
 "- BuzzASR native outputs, not the invalid original blank generic outputs, should be used for human review.",
 "- C1Tech and Qwen model outputs are candidates, not validated as accurate. User review is required.",
 "- Production Telegram bot remains unchanged.",
]
dest.parent.mkdir(exist_ok=True,parents=True)
dest.write_bytes(("\n".join(lines)+"\n").encode("utf-8"))
print("REPORT_READY",dest.name,len(lines),"lines")
