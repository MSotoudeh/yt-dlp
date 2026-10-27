$ErrorActionPreference = 'Stop'
$repo = 'C:\GitHub\yt-dlp'
$python = Join-Path $repo 'output\chatgpt\asr-venv\Scripts\python.exe'
$tokenFile = 'C:\ProgramData\ytdlp-bot\telegram-token'
$env:YTDL_TELEGRAM_BOT_TOKEN = [IO.File]::ReadAllText($tokenFile).Trim()
$allowlistFile = 'C:\ProgramData\ytdlp-bot\allowed-chat-ids'
if (-not (Test-Path -LiteralPath $allowlistFile)) {
    throw 'Bot allowlist file missing; refusing public execution'
}
$env:YTDL_ALLOWED_CHAT_IDS = [IO.File]::ReadAllText($allowlistFile).Trim()
if (-not $env:YTDL_ALLOWED_CHAT_IDS -or $env:YTDL_ALLOWED_CHAT_IDS -eq '*') {
    throw 'Bot must have a restricted allowlist'
}
$env:PYTHONPATH = Join-Path $repo 'src'
$env:PATH = 'C:\Program Files\ffmpeg\bin;' + $env:PATH
Set-Location -LiteralPath $repo
& $python -m ytdlp_tool.telegram_bot --python $python --model-dir (Join-Path $repo 'output\chatgpt\asr-models') --root 'C:\ProgramData\ytdlp-bot\state'
exit $LASTEXITCODE
