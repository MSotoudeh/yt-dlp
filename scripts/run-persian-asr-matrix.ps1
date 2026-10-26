$ErrorActionPreference='Continue'
$root='C:\GitHub\yt-dlp'
$base='C:\ProgramData\ytdlp-bot\asr-four-models'
New-Item -ItemType Directory -Force -Path $base | Out-Null
$python="$root\output\chatgpt\asr-comparison-venv\Scripts\python.exe"
$env:PYTHONIOENCODING='utf-8'
$env:HF_HOME="$root\output\chatgpt\asr-models-hf"
$source=Get-ChildItem 'C:\ProgramData\ytdlp-bot\transcribe-validation' -Recurse -Filter '*.mp3' -File|Select-Object -First 1 -ExpandProperty FullName
if(-not $source){throw 'Reference audio not found'}
$wav=Join-Path $base 'input-16000.wav'
if(-not (Test-Path $wav)){
  & ffmpeg -nostdin -hide_banner -loglevel error -y -i $source -ac 1 -ar 16000 $wav
  if($LASTEXITCODE -ne 0){throw 'FFmpeg conversion failed'}
}
$tests=@(
  @('c1tech','cpu'),@('c1tech','cuda'),
  @('buzz','cpu'),@('buzz','cuda'),
  @('cv17','cpu'),@('cv17','cuda'),
  @('qwen','cpu'),@('qwen','cuda')
)
foreach($row in $tests){
  $id=$row[0];$device=$row[1]
  $file=Join-Path $base "$id-$device.json"
  if(Test-Path $file){
    try { $state=Get-Content $file -Raw -Encoding UTF8|ConvertFrom-Json; if($state.status -eq 'complete'){Write-Output "SKIP_COMPLETE $id $device";continue} } catch {}
  }
  Write-Output "RUN $id $device $(Get-Date -Format o)"
  & $python "$root\scripts\run-persian-asr-matrix.py" --model $id --device $device --audio $wav --output $base
  Write-Output "END $id $device EXIT=$LASTEXITCODE $(Get-Date -Format o)"
}
Write-Output "ALL_ATTEMPTS_FINISHED $(Get-Date -Format o)"
