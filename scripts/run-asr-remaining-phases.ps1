$ErrorActionPreference='Continue'
$root='C:\GitHub\yt-dlp'
$out='C:\ProgramData\ytdlp-bot\asr-four-models'
$env:HF_HOME="$root\output\chatgpt\asr-models-hf"
$env:PYTHONIOENCODING='utf-8'
$py="$root\output\chatgpt\asr-comparison-venv\Scripts\python.exe"
$buzzState=Join-Path $out 'buzz-cuda-native.json'
for($i=0;$i -lt 1440;$i++){
  if(Test-Path $buzzState){
    try{$j=Get-Content $buzzState -Raw -Encoding UTF8|ConvertFrom-Json;if($j.status -in @('complete','failed')){break}}catch{}
  }
  Start-Sleep -Seconds 5
}
Write-Output ('BUZZ_GPU_STAGE='+$j.status+' '+(Get-Date -Format o))
$short='C:\ProgramData\ytdlp-bot\whisper-12s.wav'
$shortOut='C:\ProgramData\ytdlp-bot\asr-qwen-cuda-smoke'
Write-Output ('QWEN_GPU_SHORT_START='+(Get-Date -Format o))
& $py "$root\scripts\run-persian-asr-matrix.py" --model qwen --device cuda --audio $short --output $shortOut
$shortExit=$LASTEXITCODE
Write-Output ('QWEN_GPU_SHORT_EXIT='+$shortExit)
if($shortExit -eq 0){
  Write-Output ('QWEN_GPU_FULL_START='+(Get-Date -Format o))
  & $py "$root\scripts\run-persian-asr-matrix.py" --model qwen --device cuda --audio "$out\input-16000.wav" --output $out
  Write-Output ('QWEN_GPU_FULL_EXIT='+$LASTEXITCODE)
}else{
  if(Test-Path "$shortOut\qwen-cuda.json"){Copy-Item "$shortOut\qwen-cuda.json" "$out\qwen-cuda-smoke-failure.json" -Force}
  Write-Output 'QWEN_GPU_FULL_SKIPPED_AFTER_FAILED_SMOKE'
}
Write-Output ('BUZZ_CPU_NATIVE_START='+(Get-Date -Format o))
& $py "$root\scripts\run-buzzasr-native.py" --device cpu --audio "$out\input-16000.wav" --output $out
Write-Output ('BUZZ_CPU_NATIVE_EXIT='+$LASTEXITCODE)
Write-Output ('REMAINING_PHASE_COMPLETE='+(Get-Date -Format o))
