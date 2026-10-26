# Persian ASR: six-candidate GPU continuation (2026-10-21)

## Input, environment, restrictions
- Ops: Windows, NVIDIA RTX 3050 Laptop GPU with 4 GiB VRAM.
- Same unchanged 16 kHz mono audio: `C:\ProgramData\ytdlp-bot\asr-four-models\input-16000.wav` (530.1s, 19 consecutive 28s chunks).
- **GPU-only inference.** If CUDA is unavailable, fail instead of falling back to CPU.
- Local model files; model **download** uses Hugging Face but no remotely hosted speech-to-text inference/API.
- Never modify the deployed Telegram bot or the pre-existing C1Tech Base and production Whisper weight stores.
- Baselines: C1Tech Base CUDA 241.19s, Persian v4 CUDA 368.77s, Amir CV17 INT8 CUDA 379.84s (different backends/decoding; timings not directly comparable without normalizing settings).
- Do **not** claim an ASR winner or WER/CER until human-corrected ground truth exists.

## Reproducibility and checkpoints
- Worker: `scripts/benchmark-persian-six-gpu.py --model NAME` (name in givia, gholizadeh, qwen06, wav2vec, meta, nvidia).
- Controller: `scripts/run-persian-six-gpu-batch.py`, which waits for the existing Givia job then launches remaining jobs strictly sequentially.
- Output: `C:\ProgramData\ytdlp-bot\asr-six-gpu-20261021` (individual JSON status, partial transcripts, final transcripts, per-run evidence, `batch.json` and final ZIP).
- Dedicated cache: `C:\GitHub\yt-dlp\output\chatgpt\asr-six-model-hf` (git ignored).
- Project IR Givia durable long job: `78eb5da3f05848cbb05d5491a2c4623f`.
- Project IR sequential supervisor long job: `9551031e38c6485b83d7b204708e451f`.
- C1Tech Small approval watcher (independent): `af770de5f2be4826b5d385dce96ed61b` (model publisher approval remains required).

## Candidate models
| Alias | Repo | Execution |
|---|---|---|
| givia | givia/whisper-large-v3-turbo-persian | Hugging Face GGML model, preexisting whisper.cpp with CUDA |
| gholizadeh | MohammadGholizadeh/whisper-large-v3-turbo-persian | PyTorch Transformers FP16 CUDA |
| qwen06 | Qwen/Qwen3-ASR-0.6B | qwen_asr Transformers FP16 CUDA |
| wav2vec | m3hrdadfi/wav2vec2-large-xlsr-persian-v3 | PyTorch CTC CUDA |
| meta | facebook/omniASR-CTC-300M | **Blocked on native Windows**: fairseq2 only supported on Linux/WSL2 |
| nvidia | nvidia/stt_fa_fastconformer_hybrid_large | **Blocked on native Windows**: NeMo ASR Linux/WSL2 |

The blocked models are not counted as completed inference; do not misrepresent support.

## Validation
- `py -m pytest -q`: 45 passed before deployment of the trial scripts.
- Both scripts passed `py_compile`.
- CUDA whisper.cpp log for first Givia segment reports **using CUDA0 backend**, with 1,623.92 MB model weights on the GPU; first chunk produced non-empty Persian text.
- This is currently an **execution checkpoint**, not a completed quality ranking.
- Do not run two GPU jobs concurrently. If publisher approves C1Tech Small mid-batch, coordinate GPU access first.

## Recovery notes (2026-10-21)
- First Givia GPU run decoded segments 1 and 2, then hit a per-segment 200s timeout on segment 3 while beam search was set to 5. This is an execution timeout, **not an accuracy finding**. CUDA0 usage was verified in the first-segment log.
- Retry changes: Givia uses beam=1/best_of=1 and a 600s per-segment ceiling to reduce decode cost. No CPU inference allowed.
- Initial MohammadGholizadeh run failed before GPU inference because its fine-tuned checkpoint does not bundle the full Whisper vocabulary/merges files needed by the slow tokenizer. Retry instead sources the official original `openai/whisper-large-v3-turbo` processor, while retaining the Persian fine-tuned **model weights**.
- The serial supervisor is running and moved on to Qwen3-ASR 0.6B. After all first-pass model attempts, a dedicated retry supervisor reruns only Gholizadeh and Givia if not completed, validates a final ZIP, and attempts private Telegram delivery to the unique previously verified recipient.
- Retry/Telegram durable run id: `234592fe0db04316bc06b615c3864d45`. Never paste any local Hugging Face or Telegram token into chat or Git.
