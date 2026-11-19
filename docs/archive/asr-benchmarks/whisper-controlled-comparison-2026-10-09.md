# Controlled Whisper large-v3 CPU vs GPU result — 2026-10-09

Source video: https://youtu.be/m8ElotVbO6M (~8:50). Both used the same pre-downloaded MP3 on Ops, cached Systran faster-whisper-large-v3 model, language fa, beam_size 5, VAD on, condition_on_previous_text false. CPU int8; GPU int8_float16.

| Metric | CPU | GPU |
|---|---:|---:|
| Audio decode | 4.57 s | 4.21 s |
| Model load | 285.30 s | 60.26 s |
| Inference | 2688.09 s | 599.31 s |
| Total | 2977.96 s (49m37.96s) | 663.78 s (11m03.78s) |
| Segments | 142 | 148 |
| Characters | 8895 | 8869 |
| Whitespace-tokenized Unicode word count | 1930 | 1916 |

Total speedup 4.486x, inference-only speedup ~4.485x. Relative reduction in elapsed time ~77.7%. This is a controlled same-input/model comparison but different numerical precision by hardware.

The normalized token-order similarity calculated with Python difflib SequenceMatcher(autojunk=False) is 0.9173, 1764 matching words and 123 difference blocks. This **does not measure transcription accuracy**. No human-corrected reference is available to compute word error rate. Neither CPU nor GPU can be declared more accurate. Some differences include Persian number glyph conventions, spelling, joining and segmentation.

The results and complete transcripts are retained on Ops:
- `C:\ProgramData\ytdlp-bot\bench-cpu-full\cpu-metrics.json`
- `C:\ProgramData\ytdlp-bot\bench-cpu-full\cpu-transcript.txt`
- `C:\ProgramData\ytdlp-bot\bench-gpu-full\cuda-metrics.json`
- `C:\ProgramData\ytdlp-bot\bench-gpu-full\cuda-transcript.txt`
- `C:\ProgramData\ytdlp-bot\benchmark-comparison.json`

Scripts: `scripts/benchmark-whisper-cpu-gpu.py` and `scripts/compare-whisper-benchmarks.py`.

Bot production remains CPU-only; migration requires a tested GPU execution path, sustained DLL setup, failure fallback and clean deployment.