$ErrorActionPreference = 'Stop'
$repo = 'C:\GitHub\yt-dlp'
$python = Join-Path $repo 'output\chatgpt\asr-venv\Scripts\python.exe'
$tokenFile = 'C:\ProgramData\ytdlp-bot\telegram-token'
$env:YTDL_TELEGRAM_BOT_TOKEN = [IO.File]::ReadAllText($tokenFile).Trim()
$env:YTDL_ALLOWED_CHAT_IDS = '*'
$env:PYTHONPATH = Join-Path $repo 'src'
$env:PATH = 'C:\Program Files\ffmpeg\bin;' + $env:PATH
Set-Location -LiteralPath $repo
& $python -m ytdlp_tool.telegram_bot --python $python --model-dir (Join-Path $repo 'output\chatgpt\asr-models') --root 'C:\ProgramData\ytdlp-bot\state'
exit $LASTEXITCODE
