# Local-only Persian ASR candidate evaluation — Ops, 2026-10-09

## Policy and decision rule

- **No third-party/cloud speech recognition API.** All inference must run locally on Ops, offline after model downloads. Hugging Face is used only to obtain public model files; Telegram is used only as a transport for privately sharing generated files.
- Never migrate the production `YTDLP-Independent-Telegram-Bot` away from its present stable CPU processing configuration until the user approves a proven candidate.
- Never delete models, runtimes or generated transcripts until the user verifies acceptance/rejection.
- User has said that published WER ~21% is much too high, but **has not specified an exact maximum WER**. A **provisional** 3% WER acceptance gate is configured (based on our earlier discussion), with a minimum five hand-corrected, 28-second chunks. Numerical passage alone is not production approval; incorrect scientific names, numbers or units remain disqualifying without explicit user acceptance.
- Scores cannot be computed from only two model outputs or model-vs-model agreement. A human-corrected gold reference from **this exact video** is required. YouTube metadata was checked: this video has no manual subtitle languages, and the Persian auto-caption track was not available either, so a reliable existing ground-truth track could not be obtained.

## Hardware

Ops: RTX 3050 Laptop GPU, 4 GiB VRAM; CPU 20 logical processors, 40 GiB RAM. Python 3.14; PyTorch CUDA 2.14.1+cu130 and sherpa-onnx 1.13.8.

Source: https://youtu.be/m8ElotVbO6M (8 minutes 50 seconds), converted locally to 16 kHz mono WAV.
For fine-tuned models, 19 consecutive non-overlapping chunks of 28 seconds were used. Output is the raw transcript per chunk; no generative rewriting or API calls.

## Results

| Offline model | CPU, total elapsed | GPU, total elapsed | Text output |
|---|---:|---:|---|
| C1Tech Whisper Base Persian | 20m 14s | 4m 01s | Complete, both devices |
| BuzzASR Persian (**native generator**, not generic Whisper prompt) | 12m 39s | 3m 51s | Complete, both devices |
| Qwen3-ASR 1.7B | 63m 15s | 24m 44s | Complete, both devices |
| Shenava Koochik v1.0 sherpa-onnx (FastConformer-CTC, 114M) | **23.41s** | Not tested (CPU ONNX runner) | Complete, CPU |
| Whisper Large-v3 generic baseline (faster-whisper) | 49m 38s | 11m 04s | Complete, different decoding pipeline |
| CV17 Persian Whisper Large-v3 | Not available (gated weights) | Not available (gated weights) | Requires model-owner/HF authorization |

Wall times contain model load and 19-chunk inference where indicated; do not directly compare generic Whisper's segmenter/VAD pipeline with fixed-size chunks without caveats.
Shenava was tested with sherpa-onnx OfflineRecognizer.from_nemo_ctc, num_threads=8, metadata-driven log-mel preprocessing (no unsupported feature normalization).
The published source checkpoint's WER (7.49%/10.64% in its benchmark sets) is **not** performance measured on this video.

### Critical quality findings from direct transcript inspection

Even on the clearly spoken opening ~28 seconds, all candidates make recognizably incorrect substitutions or misspellings, e.g. variants of “میکروویو”, “خط‌کش”, “اندازه‌گیری”, “ذوب”, and speaker-context phrases. Qwen produced especially problematic substitutions in some opening phrases. BuzzASR initially output blank text because the generic Whisper forced-language path was wrong; the model's official generation recipe fixed that.
**None of the candidates has been certified to meet a near-perfect Persian accuracy requirement.**

## Reproducible hand scoring with no remote API

A private ZIP bundle, `Persian-ASR-offline-human-review.zip`, contains an **offline** `index.html`, the actual source MP3, and all seven valid 28-second-chunk transcripts (CPU/GPU variants). The HTML enables playback by 28-second chunk, entering verbatim corrected Persian, comparing side by side, and calculating CER/WER entirely in the local browser. The exported `persian_asr_gold_reference.json` can also be scored fully offline on Ops:

```powershell
$p='C:\GitHub\yt-dlp'
$py="$p\output\chatgpt\asr-comparison-venv\Scripts\python.exe"
& $py "$p\scripts\evaluate-persian-asr-gold.py" --reference 'PATH_TO_corrected_reference.json' --max-wer 3 --min-reviewed-chunks 5 --report 'C:\ProgramData\ytdlp-bot\asr-benchmark-delivery\gold-scored.json'
```

The 3% limit is provisional. Real acceptance must be user-approved, and critical scientific vocabulary/figures require a separate manual check.

## Private delivery

The three-model final historical ZIP was delivered to the same previously verified Telegram chat. A newer 7-output offline-review ZIP was likewise sent via the existing bot, with no bot code, stored token, chat IDs or private user content committed to Git.
Local reports: `C:\ProgramData\ytdlp-bot\asr-four-models` and `C:\ProgramData\ytdlp-bot\asr-benchmark-delivery`.

## Next decision

1. Obtain actual corrected samples in `persian_asr_gold_reference.json` (ideally all 19 chunks, at least 5 including numerals and physics names). The user can export this from the offline review page.
2. Score each model against the gold reference and inspect errors in numeric and named-entity recognition.
3. If no model meets the user's confirmed acceptance criteria, retire **the experiment** (without damaging the existing working bot); remove optional model weights and isolated experimental virtual environment only **after approval to clean them up**.
4. If a local model meets the bar, then design/test a separate CPU or GPU production feature behind an opt-in switch with rollback; do not silently replace the existing bot pipeline.
