$ErrorActionPreference='Continue'
$root='C:\GitHub\yt-dlp'
$out='C:\ProgramData\ytdlp-bot\asr-four-models'
$py="$root\output\chatgpt\asr-comparison-venv\Scripts\python.exe"
$waiting=Join-Path $out 'buzz-cpu-native.json'
$deadline=(Get-Date).AddHours(18)
while((Get-Date)-lt $deadline){
 if(Test-Path $waiting){
  try{
   $state=Get-Content $waiting -Raw -Encoding UTF8|ConvertFrom-Json
   if($state.status -in @('complete','failed')){break}
  }catch{}
 }
 Start-Sleep -Seconds 30
}
if(-not(Test-Path $waiting)){throw 'Buzz CPU native was not attempted before deadline'}
if($state.status -notin @('complete','failed')){throw 'Buzz CPU native still unfinished'}
Write-Output ('BENCHMARKS_TERMINAL='+(Get-Date -Format o))
& $py "$root\scripts\package-asr-transcripts.py" --phase final
Write-Output ('DELIVERY_EXIT='+$LASTEXITCODE)
& $py "$root\scripts\summarize-asr-evaluation.py"
Write-Output ('DOC_EXIT='+$LASTEXITCODE)
& $py -m py_compile "$root\scripts\run-persian-asr-matrix.py" "$root\scripts\run-buzzasr-native.py" "$root\scripts\package-asr-transcripts.py" "$root\scripts\summarize-asr-evaluation.py"
Write-Output ('SCRIPT_COMPILE_EXIT='+$LASTEXITCODE)
Set-Location $root
& python -m pytest tests -q -p no:cacheprovider
Write-Output ('PYTEST_EXIT='+$LASTEXITCODE)
& git add -- 'scripts/run-persian-asr-matrix.py' 'scripts/run-persian-asr-matrix.ps1' 'scripts/run-persian-asr-gpu-followup.ps1' 'scripts/run-asr-remaining-phases.ps1' 'scripts/run-buzzasr-native.py' 'scripts/qwen-gpu-oom-recovery.ps1' 'scripts/package-asr-transcripts.py' 'scripts/summarize-asr-evaluation.py' 'scripts/finalize-persian-asr-matrix.ps1' 'docs/persian-asr-four-models-2026-10-09.md'
& git diff --cached --check
if($LASTEXITCODE -eq 0){
 & git diff --cached --quiet
 if($LASTEXITCODE -ne 0){
  & git commit -m 'bench: record Persian ASR model comparisons and secure output delivery'
  Write-Output ('COMMIT_EXIT='+$LASTEXITCODE)
  & git push
  Write-Output ('PUSH_EXIT='+$LASTEXITCODE)
 }
}
Write-Output 'FINALIZER_DONE'
