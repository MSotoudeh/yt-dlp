# Whisper large-v3 GPU benchmark — Ops, 2026-10-09

## Hardware / reproducibility

- NVIDIA RTX 3050 Laptop GPU, 4 GiB VRAM, NVIDIA driver 596.08
- Windows, ASR Python environment at `output/chatgpt/asr-venv`
- faster-whisper 1.2.1, CTranslate2 4.8.2
- NVIDIA CUDA runtime 12.6.77, cuBLAS 12.6.4.1, cuDNN 9.10.2.21
- GPU support requires CUDA DLL directories and explicit preload inside process. See `scripts/benchmark-whisper-cpu-gpu.py`; Python model loading alone is NOT proof of working inference.
- Model: local cached Systran faster-whisper **large-v3**
- Source: https://youtu.be/m8ElotVbO6M (8 min 50 sec), using downloaded MP3 already on Ops
- Language `fa`, beam_size 5, VAD true, condition_on_previous_text false. CPU baseline configured for int8; GPU tested with int8_float16.

## GPU measured results

- decode 4.21s
- load 60.26s
- inference 599.31s
- end-to-end local audio->text 663.78s (11m04s)
- 148 segments, 8869 characters
- output: `C:\ProgramData\ytdlp-bot\bench-gpu-full\cuda-transcript.txt`
- machine-readable metrics: `C:\ProgramData\ytdlp-bot\bench-gpu-full\cuda-metrics.json`

## CPU comparison qualification

User-observed prior complete Telegram bot request lasted **about 17m**. GPU local inference + decode + model load was **11m04s**. An indicative comparison is ~1.54x speedup (~35% less time), but the CPU number includes Telegram and download overhead; it is **not a fully controlled A/B experiment**. For a fair exact benchmark, run the script on the same pre-downloaded file with `--device cpu` and compare `total_seconds` and `inference_seconds`.

No measured accuracy advantage is asserted: GPU and CPU both use large-v3 but different compute types. Compare output against corrected reference transcript for word error rate.

## Deployment status

The production Telegram bot still runs with CPU configured in `src/ytdlp_tool/transcribe.py`. GPU was tested separately; do not change production default until resilience, error handling, and fallback are implemented and tested. No Cloudflare resources required for this benchmark.
