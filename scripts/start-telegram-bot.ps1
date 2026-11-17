# Starts the private Telegram bot (run by the scheduled task; see docs/operations.md).
# Logs live in $stateDir: bot.log (bot + launcher), bot.out.log, bot.stderr.log -> a stopped bot is always explainable.
$ErrorActionPreference = 'Stop'
$repo = 'C:\GitHub\yt-dlp'
$python = Join-Path $repo 'output\chatgpt\asr-venv\Scripts\python.exe'
$secretsDir = 'C:\ProgramData\ytdlp-bot'
$stateDir = Join-Path $secretsDir 'state'
$tokenFile = Join-Path $secretsDir 'telegram-token'
$allowlistFile = Join-Path $secretsDir 'allowed-chat-ids'
$maxLogBytes = 5MB

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$errLog = Join-Path $stateDir 'bot.log'
$outLog = Join-Path $stateDir 'bot.out.log'
$stderrLog = Join-Path $stateDir 'bot.stderr.log'

function Write-BotLog([string]$message) {
    Add-Content -LiteralPath $errLog -Value ('{0} launcher: {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message)
}

# Keep the two logs bounded: one previous generation is enough for diagnosis.
foreach ($log in @($errLog, $outLog, $stderrLog)) {
    if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt $maxLogBytes) {
        Move-Item -LiteralPath $log -Destination ($log + '.1') -Force
    }
}

try {
    if (-not (Test-Path -LiteralPath $tokenFile)) { throw 'Bot token file missing' }
    if (-not (Test-Path -LiteralPath $allowlistFile)) {
        throw 'Bot allowlist file missing; refusing public execution'
    }
    $env:YTDL_TELEGRAM_BOT_TOKEN = [IO.File]::ReadAllText($tokenFile).Trim()
    $env:YTDL_ALLOWED_CHAT_IDS = [IO.File]::ReadAllText($allowlistFile).Trim()
    if (-not $env:YTDL_ALLOWED_CHAT_IDS -or $env:YTDL_ALLOWED_CHAT_IDS -eq '*') {
        throw 'Bot must have a restricted allowlist'
    }
    $env:PYTHONPATH = Join-Path $repo 'src'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PATH = 'C:\Program Files\ffmpeg\bin;' + $env:PATH
    Set-Location -LiteralPath $repo

    Write-BotLog 'starting bot process'
    # Start-Process keeps native stderr out of PowerShell's error stream, which would
    # otherwise abort this script under $ErrorActionPreference = 'Stop'.
    # The bot itself appends its own log lines to bot.log (--log-file); the redirected
    # streams only capture what escapes it (interpreter crashes, import errors).
    $arguments = @(
        '-m', 'ytdlp_tool.telegram_bot',
        '--python', ('"{0}"' -f $python),
        '--model-dir', ('"{0}"' -f (Join-Path $repo 'output\chatgpt\asr-models')),
        '--root', ('"{0}"' -f $stateDir),
        '--log-file', ('"{0}"' -f $errLog)
    )
    $process = Start-Process -FilePath $python -ArgumentList $arguments -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $outLog -RedirectStandardError $stderrLog
    Write-BotLog ('bot process exited with code {0}' -f $process.ExitCode)
    exit $process.ExitCode
} catch {
    Write-BotLog ('launcher failed: {0}' -f $_.Exception.Message)
    exit 1
}
