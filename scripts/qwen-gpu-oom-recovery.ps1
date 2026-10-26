$ErrorActionPreference='Continue'
$out='C:\ProgramData\ytdlp-bot\asr-four-models'
$file=Join-Path $out 'qwen-cuda.json'
$deadline=(Get-Date).AddHours(3)
while((Get-Date)-lt $deadline){
 if(Test-Path $file){
  try{$s=Get-Content $file -Raw -Encoding UTF8|ConvertFrom-Json;if($s.status -in @('failed','complete')){break}}catch{}
 }
 Start-Sleep -Seconds 20
}
if($s.status -eq 'complete'){Write-Output 'QWEN_GPU_ALREADY_COMPLETE';exit 0}
if($s.status -ne 'failed'){Write-Output 'QWEN_GPU_NOT_TERMINAL';exit 3}
if(([string]$s.error) -notmatch 'out of memory|CUDA.*memory'){Write-Output 'QWEN_GPU_FAILED_NOT_OOM';exit 0}
Write-Output ('QWEN_GPU_OOM_RETRY_CHUNKS_12 '+(Get-Date -Format o))
$py='C:\GitHub\yt-dlp\output\chatgpt\asr-comparison-venv\Scripts\python.exe'
$env:HF_HOME='C:\GitHub\yt-dlp\output\chatgpt\asr-models-hf'
$env:PYTHONIOENCODING='utf-8'
$target='C:\ProgramData\ytdlp-bot\asr-qwen-gpu-12s-fallback'
& $py 'C:\GitHub\yt-dlp\scripts\run-persian-asr-matrix.py' --model qwen --device cuda --audio "$out\input-16000.wav" --output $target --chunk-seconds 12
Write-Output ('QWEN_GPU_FALLBACK_EXIT='+$LASTEXITCODE)
if($LASTEXITCODE -eq 0){
  Copy-Item "$target\qwen-cuda.json" "$out\qwen-cuda.json" -Force
  Copy-Item "$target\qwen-cuda.txt" "$out\qwen-cuda.txt" -Force
  Write-Output 'QWEN_GPU_FALLBACK_VALIDATED_AND_PROMOTED'
}
