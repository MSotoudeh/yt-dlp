# Final checkpoint — offline Persian ASR GPU benchmark (2026-10-22)

## Result and evidence

The full source was the unchanged 530.1-second, 16 kHz mono WAV at
`C:\ProgramData\ytdlp-bot\asr-four-models\input-16000.wav`.
It was evaluated in 19 successive segments, each at most 28 seconds.

| Model | GPU trial | Reported wall time | Interpretation |
|---|---|---:|---|
| C1Tech Base (existing reference) | 19/19 complete | 241.19s | Earlier result |
| Persian v4 (existing reference) | 19/19 complete | 368.77s | Earlier CT2 int8_float16 |
| AmirMohseni CV17 (existing reference) | 19/19 complete | 379.84s | Earlier CT2 int8_float16 |
| m3hrdadfi Wav2Vec2 Persian v3 | **19/19 complete** | 231.84s | Initial cold run, includes download/loading |
| MohammadGholizadeh Turbo Persian | **19/19 complete** | 769.89s | Fixed tokenizer, includes download/loading |
| Qwen3-ASR 0.6B | **19/19 complete** | 1426.59s | Initial cold run, includes download/loading |
| Givia Whisper Turbo Persian | **19/19 complete** | **159.48s for ONLY final 4 chunks** | Resumed from checkpoint of 15 previously completed chunks; not a valid full-run timing |
| Meta Omnilingual CTC-300M | not attempted | — | Native Windows fairseq2 unsupported; Linux needed |
| NVIDIA Persian FastConformer hybrid large | not attempted | — | Native Windows NeMo ASR unsupported; Linux needed |
| C1Tech Small Persian | not attempted | — | Gated repository author approval still pending (403 on October 22) |

The durations use different ASR runtimes, decoding algorithms, model load states, and downloads. They are **not** apples-to-apples speed figures. No reliable objective accuracy comparison is available without **manual ground truth**, despite 19/19 technical success.

## Recovered bugs / caveats
- Givia's first run timed out with beam=5 on chunk 3. Retried at beam=1 (GPU verified by whisper.cpp CUDA backend log).
- The 19-chunk Givia transcription was completed using the 15 correctly preserved chunks of the second run plus chunks 16–19 on October 22. Chunk 16 had exactly **one invalid UTF-8 byte sequence**, decoded with one U+FFFD replacement; the 576 original bytes were retained in `givia-segment-16-raw.bin` and warning in `givia-encoding-warnings.jsonl`.
- The model's 159.48-second final JSON `seconds` field covers the **resumed final four chunks**, not the complete source. Treat it as resumed-session elapsed time only.
- The initial Gholizadeh failed run left stale `error` and `traceback` keys in the same JSON even after successful retry. The authoritative `status=complete, chunks=19` is correct; earlier failure was solved by using official `openai/whisper-large-v3-turbo` processor with Persian fine-tuned checkpoint weights. The benchmark's `report()` code now removes stale error fields on subsequent successful runs.
- No GPU job overlap occurred in the sequential batch and recovery; the Telegram production bot and its model weights were not changed.

## Deliverables

1. Previously delivered to verified private Telegram recipient: `Persian-ASR-Six-GPU-Comparison.zip` (33,822 bytes). Includes 6 complete raw transcripts (three existing, Gholizadeh, Qwen, Wav2Vec2; excludes Givia because it failed then).
2. **Delivered successfully on 2026-10-22**: `Persian-ASR-GPU-Offline-Human-Review-20261022.zip` (16,182,142 bytes). Exactly 7 complete model transcripts + original WAV + offline `index.html` for listening to each 28s chunk, human transcription correction and WER/CER calculation only for corrected chunks. Includes the Givia transcript. Verified ZIP CRC, 19 chunks for every model, and JavaScript syntax via Node.
3. Reviewer's corrections may be exported as `persian_asr_gold_reference.json` with 19 `references` and a source identifier; no accuracy claim before these are populated.

All recorded evidence is on Ops at `C:\ProgramData\ytdlp-bot\asr-six-gpu-20261021`. The UTF-8 byte-corruption evidence is retained locally, not silently dropped.

## Constraints respected

- Inference on RTX 3050 GPU; no CPU fallback for ASR.
- No paid speech-to-text APIs.
- Production bot untouched.
- No deletion of baseline/production model weights.
- No model selected as best in the absence of ground truth.

## Suggested next experimental protocol

Obtain a human-corrected reference for at least five diverse 28s segments, including early and late science terminology and numerical statements. More coverage reduces sampling bias. Then calculate normalized WER and CER and separately score wrong numbers, units, and proper names. Reject models failing the user's chosen threshold. Do not interpret agreement with C1Tech Base as truth.
