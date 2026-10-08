"""Benchmark faster-whisper on the same input and model, CPU vs CUDA.

Run with ASR venv from the yt-dlp repository. Saves a machine-readable JSON
result and UTF-8 transcript; no tokens or user credentials are used.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import time

def cuda_libraries():
    site = Path(sys.executable).resolve().parents[1] / "Lib" / "site-packages"
    roots = [site / "nvidia"]
    handles = []
    dirs = []
    for root in roots:
        for dll in root.rglob("*.dll"):
            if dll.name.lower().startswith(("cublas", "cudnn", "cudart")):
                folder = str(dll.parent)
                if folder not in dirs:
                    dirs.append(folder)
                    handles.append(os.add_dll_directory(folder))
    # CTranslate2 loads cuBLAS with LoadLibrary at inference time on Windows.
    # Both PATH and explicit dependency preloading are needed for its DLL lookup.
    os.environ['PATH'] = os.pathsep.join(dirs) + os.pathsep + os.environ['PATH']
    for name in ('cudart64_12.dll', 'cublasLt64_12.dll', 'cublas64_12.dll', 'cudnn64_9.dll'):
        matches = list(root.rglob(name))
        if matches:
            ctypes.WinDLL(str(matches[0]))
    # Keep add_dll_directory handles alive for the entire inference.
    if not dirs:
        raise RuntimeError("No NVIDIA CUDA DLLs found in ASR environment")
    return handles, dirs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--device", choices=["cpu", "cuda"], required=True)
    p.add_argument("--model", default="large-v3")
    p.add_argument("--model-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--language", default="fa")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    dll_dirs = []
    if args.device == "cuda":
        handles, dll_dirs = cuda_libraries()
        print("CUDA_DLL_PATHS", len(dll_dirs), flush=True)
    from faster_whisper import WhisperModel
    from ytdlp_tool.transcribe import _decode_pcm
    audio = _decode_pcm(Path(args.audio))
    t_decode = time.perf_counter()
    print("AUDIO_DECODE_SECONDS", round(t_decode-t0,2), flush=True)
    snapshots = list((Path(args.model_dir) / f'models--Systran--faster-whisper-{args.model}' / 'snapshots').glob('*'))
    model_source = str(snapshots[0]) if snapshots else args.model
    print('MODEL_SOURCE_LOCAL', bool(snapshots), flush=True)
    whisper = WhisperModel(model_source, device=args.device,
                          compute_type="int8_float16" if args.device=="cuda" else "int8",
                          cpu_threads=8, download_root=args.model_dir)
    t_loaded = time.perf_counter()
    print("MODEL_LOAD_SECONDS", round(t_loaded-t_decode,2), flush=True)
    segments, info = whisper.transcribe(
        audio, language=args.language, beam_size=5, vad_filter=True,
        condition_on_previous_text=False)
    results = list(segments)
    t_done = time.perf_counter()
    transcript = "\n".join(s.text.strip() for s in results)
    (out / f"{args.device}-transcript.txt").write_text(transcript, encoding="utf-8")
    metrics = {
        "device": args.device, "model": args.model,
        "language": info.language, "input": str(args.audio),
        "decode_seconds": round(t_decode-t0,2),
        "model_load_seconds": round(t_loaded-t_decode,2),
        "inference_seconds": round(t_done-t_loaded,2),
        "total_seconds": round(t_done-t0,2),
        "segments": len(results),
        "characters": len(transcript),
        "compute_type": "int8_float16" if args.device=="cuda" else "int8",
        "beam_size": 5, "vad_filter": True,
        "condition_on_previous_text": False
    }
    (out / f"{args.device}-metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),encoding="utf-8")
    print("METRICS", json.dumps(metrics, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
