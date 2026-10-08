# Transcription with Whisper

The `transcribe` command converts speech from public media URLs (Instagram Reels, YouTube and other yt-dlp sources) or local audio/video files into UTF-8 TXT and time-coded SRT files. Unlike `subs`, it does not require published subtitles.

## Setup on Ops (Windows)

Speech-recognition dependencies are optional, isolated from the system Python and ignored by Git.

```powershell
cd C:\GitHub\yt-dlp
python -m venv output\chatgpt\asr-venv
& .\output\chatgpt\asr-venv\Scripts\python.exe -m pip install -e ".[asr]"
ffmpeg -version
```

Whisper model weights are downloaded from Hugging Face on first use, then cached locally. Set `$env:PYTHONIOENCODING='utf-8'` if the Windows console cannot print Persian characters.

### Large-v3 on Ops

The full multilingual `faster-whisper large-v3` model is cached under `output\chatgpt\asr-models` on Ops. Its main CTranslate2 weight file is about 2.875 GiB. A local load test succeeded on CPU with `compute_type=int8` and 8 CPU threads.

Use it when transcription accuracy matters more than speed:

```powershell
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcribe "URL_OR_LOCAL_FILE" --model large-v3 --model-dir output\chatgpt\asr-models --cpu-threads 8
```

The CLI default remains `small`; downloading `large-v3` does not change normal runs unless `--model large-v3` is selected explicitly.

## Usage

```powershell
# Instagram: audio, original video, TXT and SRT
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcribe "https://www.instagram.com/reel/DeNktutiERf/" --video --output-dir output\chatgpt\transcribe --model-dir output\chatgpt\asr-models

# YouTube: audio, TXT, SRT; automatic language detection
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcribe "https://www.youtube.com/watch?v=VIDEO_ID"

# Local file: no network media download
& .\output\chatgpt\asr-venv\Scripts\python.exe -m ytdlp_tool transcribe "C:\path\audio.mp3" --lang fa --model small
```

Options: `--lang auto|fa|en|it|...` (default auto), `--model small` (default; base is faster, medium/large can be more accurate but slower), `--model-dir PATH`, `--cpu-threads 8`, `--video` (download the original video for URL sources only), and `--output-dir PATH`.

Output under the selected directory:

- `audio/<title> [<id>].mp3` for online URLs.
- `video/<title> [<id>].<ext>` with `--video` only.
- `transcripts/<audio-stem>.txt`, UTF-8 with BOM for Windows editors.
- `transcripts/<audio-stem>.srt`, UTF-8 with BOM and timestamps.

Audio is retained for manual checking. Missing speech produces an error rather than an empty success.

## Pipeline

1. yt-dlp downloads media audio; ffmpeg extracts MP3.
2. ffmpeg decodes it to mono 16kHz float32 samples.
3. faster-whisper / CTranslate2 performs multilingual speech recognition, language detection and time-aligned decoding using Whisper's Transformer architecture.
4. The toolkit writes TXT and SRT. It bypasses a PyAV decoding incompatibility observed with Python 3.14 on Ops.

## Limitations and security

- Transcripts are not guaranteed accurate: review Persian proper nouns, dates, noisy speech and fast narration.
- Online sources must be accessible to yt-dlp. Do not extract browser cookies or bypass DRM without explicit authorization.
- The model is downloaded once from Hugging Face; inference runs locally on CPU, without cloud ASR billing.
- Long files require RAM because the input is decoded to in-memory PCM.
- `subs` uses published YouTube subtitles; `transcribe` works on actual speech and supports other yt-dlp sites.
