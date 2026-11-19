# C1Tech Small GPU-only continuation (2026-10-21)

## Constraints
- User accepted the access terms for `C1Tech/whisper_small_persian` in their **existing Brave profile** on Ops.
- That browser authentication does **not** automatically provide a Hugging Face token to the independent Python benchmark.
- Brave-ops integration: use only Remote Desktop Commander with the installed BraveChatGPTBridge. As of 2026-10-21, Desktop Commander reported monthly quota exhausted. No substitute browser automation or replay against the bridge through a different tool.
- A user action is required to create a Hugging Face **read** token associated with the account that accepted the gated model terms, and to enter it **locally** on Ops. Never paste tokens into chat or commit them.

## One-time local authorization
1. Visit https://huggingface.co/settings/tokens in the existing signed-in Brave and create a read-only token, if one is not already available.
2. Open PowerShell on Ops and execute:

```powershell
& 'C:\GitHub\yt-dlp\scripts\Authorize-C1TechSmall.ps1'
```

3. At the local prompt, paste the token. Do not add it to Git credentials. The wrapper sets `HF_HOME=C:\GitHub\yt-dlp\output\chatgpt\asr-models-hf` (ignored by git).

## Autonomous continuation
- Long job `af770de5f2be4826b5d385dce96ed61b` on Project IR / Ops waits at most 12 hours for local HF authorization to become accessible.
- Once authorized, `scripts/benchmark-c1tech-small-gpu.py` downloads the gated checkpoint and evaluates exactly 19 consecutive 28-second chunks on CUDA 0, saving `C:\ProgramData\ytdlp-bot\asr-three-gpu-20261009\c1tech-small-cuda.txt` and metrics.
- No CPU inference fallback; if CUDA is unavailable, the benchmark fails clearly.
- After success, `scripts/deliver-c1tech-small-gpu.py` sends a private ZIP to the **previously verified Telegram chat** that requested the source video. Text/metrics from the C1Tech Base, CV17 CT2 INT8, and Persian v4 CUDA experiments are included.
- Model cache retained for C1Tech; previous non-C1Tech experiment model weights were removed while the original `faster-whisper-large-v3` production dependency was preserved.
- No ASR SaaS/API and no browser-cookie extraction.

## Current evidence
- Both non-gated follow-up models completed on 2026-10-09:
  - AmirMohseni/whisper-large-v3-persian-ct2-int8: 379.84 seconds CUDA.
  - nezamisafa/whisper-persian-v4: 368.77 seconds CUDA.
- Compared with C1Tech Base CUDA: 241.19 seconds, but none of these comparisons establishes WER without a corrected ground truth.
- 2026-10-21: ~37.92 GiB free in C:, PyTorch CUDA present. No C1Tech Small weights in the Python cache, no local HF token. Brave remains signed-in but unavailable to automation while its connector quota is exhausted.
- The production Telegram **scheduled task** unexpectedly showed `Ready`, last task result 1 on 2026-10-20; do not infer bot polling is online or modify that service as part of this ASR-only continuation without diagnosis and an explicit production remediation plan.

## Follow-up
After the watcher completes, inspect `c1tech-small-watcher.json` and `c1tech-small-cuda.json`; verify 19 chunks, nonblank output, private ZIP delivery marker, disk space and git status. Compare actual source audio and model text (not transcript-vs-transcript agreement alone).
