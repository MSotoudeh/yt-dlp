# Persian speech-recognition benchmarks (October 2026)

Summary of the local-only experiments run on the Ops laptop to find a better Persian speech-to-text model than the bot's default `faster-whisper large-v3`. The dated working logs are in [archive/asr-benchmarks/](archive/asr-benchmarks/); the tools are in [`scripts/asr-benchmarks/`](../scripts/asr-benchmarks/).

## Question and rules

- Can a locally run model transcribe Persian science talks accurately enough to replace `large-v3` in the bot?
- No cloud speech-to-text APIs; models are downloaded from Hugging Face and run offline. No access-control bypass for gated models.
- The production bot was never changed by these experiments.
- One test source throughout: an 8 min 50 s Persian YouTube talk, decoded to 16 kHz mono and cut into 19 consecutive 28-second chunks.
- Hardware: NVIDIA RTX 3050 Laptop GPU (4 GiB VRAM), 20 logical CPUs, 40 GiB RAM, Windows, Python 3.14.

## Results

**Whisper large-v3 (faster-whisper), CPU vs GPU**, same input and settings (`fa`, beam 5, VAD): CPU int8 49 min 38 s, GPU int8_float16 11 min 04 s (about 4.5x faster). The two transcripts agree on about 92% of words; that is agreement, not accuracy. The bot still runs on CPU because the GPU path needs explicit CUDA DLL preloading and a fallback that has not been built.

**Persian fine-tuned candidates** (wall time for all 19 chunks; backends, precision and decoding differ, so times are indicative only):

| Model | CPU | GPU | Note |
| --- | ---: | ---: | --- |
| C1Tech Whisper Base Persian | 20 m 14 s | 4 m 01 s (241 s) | owner judged it qualitatively best |
| BuzzASR Persian | 12 m 39 s | 3 m 51 s | needs its native prompt recipe; the generic Whisper path returns blank text |
| Qwen3-ASR 1.7B | 63 m 15 s | 24 m 44 s | noticeable substitutions |
| Shenava Koochik (sherpa-onnx) | 23 s | not tested | owner judged it worst |
| AmirMohseni large-v3 CT2 int8 | | 380 s | |
| nezamisafa Whisper Persian v4 (converted to CT2) | | 369 s | |
| m3hrdadfi Wav2Vec2 Persian v3 | | 232 s | cold run incl. download |
| MohammadGholizadeh Turbo Persian | | 770 s | needed the upstream turbo tokenizer |
| Qwen3-ASR 0.6B | | 1427 s | cold run incl. download |
| Givia Whisper Turbo Persian (whisper.cpp) | | resumed run, no valid total | beam 1 after a timeout at beam 5 |
| C1Tech Small, CV17 large-v3 | gated | gated | Hugging Face access not granted |
| Meta omniASR CTC-300M, NVIDIA FastConformer | | not run | need Linux (fairseq2 / NeMo) |

## Conclusion

No model can be called more accurate yet: there is **no human-corrected reference transcript**. Every candidate makes visible errors on terminology and numbers. An offline review page (`build-persian-asr-offline-review.py`) lets a reviewer listen to each chunk, correct the text and export `persian_asr_gold_reference.json`; `evaluate-persian-asr-gold.py` then scores WER/CER against it (provisional gate: 3% WER over at least five chunks). Until that review is done, the bot keeps `large-v3` on CPU.

## Tools (`scripts/asr-benchmarks/`)

These are research scripts kept as they were run: they use absolute Ops paths (`C:\GitHub\yt-dlp`, `C:\ProgramData\ytdlp-bot\...`) and a separate `output\chatgpt\asr-comparison-venv`. One-off orchestration (waiters, retries, one-time Telegram deliveries) was removed on 2026-11-19 and is available in git history at commit `0d54b85`.

| Script | Purpose |
| --- | --- |
| `benchmark-whisper-cpu-gpu.py`, `compare-whisper-benchmarks.py` | large-v3 CPU vs GPU run and comparison |
| `run-persian-asr-matrix.py` / `.ps1`, `run-buzzasr-native.py`, `run-shenava-onnx-benchmark.py` | first four-model CPU/GPU matrix |
| `run-three-persian-gpu-candidates.py`, `benchmark-new-persian-ct2-gpu.py` | second round (CT2 candidates) |
| `run-persian-six-gpu-batch.py`, `benchmark-persian-six-gpu.py` | third round (six GPU candidates) |
| `build-persian-asr-offline-review.py`, `evaluate-persian-asr-gold.py` | human review bundle and WER/CER scoring (unit-tested) |
