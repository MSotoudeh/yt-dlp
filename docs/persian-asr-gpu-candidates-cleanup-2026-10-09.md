# Persian ASR: GPU-only candidate round and selective weight cleanup — 2026-10-09

## User constraints

- Keep **C1Tech** weights; remove other *experimental* model weights to reclaim space.
- Test **C1Tech Whisper Small Persian**, **AmirMohseni CT2 INT8 Persian (CV17 derivative)**, **nezamisafa Whisper Persian v4**, **GPU only** when supported by the RTX 3050 Laptop 4 GiB.
- Preserve original MP3, previous model transcripts, reports and the production Telegram bot.
- Do not use hosted ASR inference APIs, paid models/services, unapproved access workarounds, or pretend a downloadable model has been tested if gated.

## Disk cleanup and safety

| Check | Bytes free |
|---|---:|
| Before selective cleanup | 18,261,098,496 |
| Immediately after selective cleanup | 26,520,104,960 |
| Freed by selective cleanup | **8,259,006,464** |

Removed the *experiment-only* Hugging Face cached weights for BuzzASR Persian, Qwen3-ASR 1.7B, Shenava Koochik, and the duplicate local Shenava ONNX download; also removed the unused generic `faster-whisper-small` cache. Historical transcript .txt/.json, video source audio, reports, offline evaluation bundles and C1Tech Base were retained.

**Necessary exception:** The independent production Telegram bot's `/transcribe` implementation still explicitly requests `--model large-v3`, using the cached Systran faster-whisper-large-v3. Deleting that cache would break the bot's production voice transcription. Preserve this model unless a separately validated migration replaces that production dependency. The Telegram scheduled task remained Running.

## Three GPU candidates

| Candidate | Hugging Face access | GPU plan | Outcome |
|---|---|---|---|
| C1Tech Whisper Small Persian | Gated manual access, 401 without accepted license/token on Ops | PyTorch float16 if authorized | **Blocked before download**; no authorization bypass |
| AmirMohseni/whisper-large-v3-persian-ct2-int8 | Public model.bin, ~1.55 GB | Native CTranslate2 int8_float16 on GPU | Detached job in progress |
| nezamisafa/whisper-persian-v4 | Public 6.17 GB split safetensors (FP32) | Convert locally to CT2 int8_float16, then evaluate on GPU | Queued after Amir |

Job id for restart/checkpoint: `fc2923e1bb3c45e88bd2a9a18b45d0be`, Project IR device `ops`.

The orchestrator is `scripts/run-three-persian-gpu-candidates.py`. It saves:
- `C:\ProgramData\ytdlp-bot\asr-three-gpu-20261009\*-cuda.txt` and `*-cuda.json`;
- candidate stage/error JSON files;
- an output ZIP under `C:\ProgramData\ytdlp-bot\asr-benchmark-delivery` containing the new outputs and C1Tech Base GPU baseline.

Once the GPU tests finish (success or failure), the orchestrator deletes **the newly downloaded non-C1Tech model weight caches** and the temporary V4 conversion directory, retaining the transcripts and metrics. It attempts delivery of the private ZIP to the existing Telegram chat verified for this video. No account identifier or secret is included in git.

## Quality gate

The user judges C1Tech Base qualitatively best and Shenava Koochik worst. No valid human-corrected reference is available yet; therefore speed/character counts alone cannot establish which new model is more accurate. Continue to assess scientific terminology, numbers, omissions and phonetic substitutions against the audio itself. Do not change the production bot before the user explicitly accepts a new model.

## Restoring access to C1Tech Small

Official model page: https://huggingface.co/C1Tech/whisper_small_persian . A human must accept the gated model owner's terms under an account authorized for weights, then authenticate that account on Ops for a local download; do not send access tokens into a chat.
