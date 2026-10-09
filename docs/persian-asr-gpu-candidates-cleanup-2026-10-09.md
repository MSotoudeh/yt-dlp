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

## Final GPU results (2026-10-09)

The detached run `fc2923e1bb3c45e88bd2a9a18b45d0be` completed with exit code 0 in approximately 32 minutes. No cloud ASR API was used.

- AmirMohseni CV17-derived CT2 INT8: CUDA `int8_float16`, beam 5, 19 chunks, 7,999 characters; model load 9.78 s, GPU benchmark 379.84 s, download 210.70 s, full trial 591.11 s. Status complete.
- nezamisafa Persian v4: downloaded public FP32 weights in 868.30 s, converted locally to CT2 `int8_float16` (1,551,326,177-byte model.bin); CUDA, beam 5, 19 chunks, 9,398 characters; load 7.92 s, GPU benchmark 368.77 s, full trial 1321.73 s. Status complete.
- C1Tech Small: HTTP 401 gated access; no authorized account or owner approval on Ops. No download or inference.

Neither transcript length nor speed measures recognition accuracy. Human inspection or a corrected reference is required to compare these models with C1Tech Base.

Post-run verification: both new trial model caches and temporary V4 converted weights are absent. C1Tech Base and the production large-v3 weights remain present. Disk free was 21,952,937,984 bytes at job end and 21,821,456,384 bytes later. The earlier 26,520,104,960-byte post-cleanup baseline was higher; the difference is not explained by the two trial model caches, which are absent.

Delivery verified: the 15,816-byte Persian-ASR-next-three-GPU-comparison.zip passed zipfile.testzip(). It contains both new GPU transcripts and metrics plus C1Tech Base reference and a summary of the gated model. The detached job reported DELIVERED_PRIVATE_TELEGRAM_OK and wrote a delivery marker; no duplicate send was attempted.

Tests: python -m pytest -q tests/test_evaluate_persian_asr_gold.py tests/test_transcribe.py: 10 passed in 0.49 s. Local GPU electricity cost not metered; no cloud ASR API used.

Production bot warning: the Windows task YTDLP-Independent-Telegram-Bot was Ready, LastTaskResult=1, last run 2026-10-08 23:26:05, with no running telegram_bot Python process at the final check. It had appeared Running earlier. No production bot or model was changed or restarted; the observed change cannot be causally attributed to the ASR tests without separate diagnosis.
