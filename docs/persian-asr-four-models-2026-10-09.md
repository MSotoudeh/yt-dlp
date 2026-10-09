# Persian ASR four-model evaluation — 2026-10-09

## Method

- Input: https://youtu.be/m8ElotVbO6M (~8:50), same locally decoded 16 kHz mono WAV.
- Source text judged by the user; this experiment does not have a gold-reference WER or CER.
- Four candidate checkpoints, each tested independently on CPU and (if possible) RTX 3050 4 GiB CUDA GPU.
- Both paths use 28-second non-overlapping chunks, except short hardware smoke tests.
- CPU uses float32 and GPU float16 where supported. Numerical differences may affect transcription.
- Model instructions, access policy and memory capacity may preclude a valid transcript.
- BuzzASR requires its native generation prompt; a generic forced-language run produced empty output and is INVALID.

## Benchmark

| Model | Device | Result | Wall time | Characters | Notes |
|---|---|---|---:|---:|---|
| C1Tech Whisper Base Persian | CPU | valid_txt | 20.23 min | 8998 |  |
| C1Tech Whisper Base Persian | CUDA | valid_txt | 4.02 min | 8994 |  |
| BuzzASR Persian | CPU | valid_txt | 12.66 min | 8703 |  |
| BuzzASR Persian | CUDA | valid_txt | 3.85 min | 8703 |  |
| Whisper Large-v3 Persian CV17 | CPU | failed | 0.32 min | — | You are trying to access a gated repo. Make sure to have access to it at https://huggingface.co/MohammadGholizadeh/whisper-large-v3-persian- |
| Whisper Large-v3 Persian CV17 | CUDA | failed | 0.03 min | — | CUDA unavailable in PyTorch environment |
| Qwen3-ASR 1.7B | CPU | valid_txt | 63.26 min | 8229 |  |
| Qwen3-ASR 1.7B | CUDA | valid_txt | 24.73 min | 8223 |  |

## Delivery and limitations

- Valid TXT outputs and a per-run status report are placed in a private ZIP bundle and sent only to the previously verified Telegram chat that submitted this video's /transcribe request.
- These transcript texts are **not** committed to a public repository.
- CV17 model weights currently require gated Hugging Face authorization; its public model card alone is insufficient.
- BuzzASR native outputs, not the invalid original blank generic outputs, should be used for human review.
- C1Tech and Qwen model outputs are candidates, not validated as accurate. User review is required.
- Production Telegram bot remains unchanged.
