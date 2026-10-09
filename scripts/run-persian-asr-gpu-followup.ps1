$ErrorActionPreference='Continue'
$root='C:\GitHub\yt-dlp'
$base='C:\ProgramData\ytdlp-bot\asr-four-models'
$python="$root\output\chatgpt\asr-comparison-venv\Scripts\python.exe"
for($i=0;$i -lt 720;$i++){
 if(-not(Get-Process -Id 9392 -ErrorAction SilentlyContinue)){break}
 Start-Sleep -Seconds 60
}
Write-Output "CPU_PHASE_END_CHECK $(Get-Date -Format o)"
& $python -m pip install --disable-pip-version-check --index-url https://download.pytorch.org/whl/cu130 'torch==2.14.1+cu130'
Write-Output "GPU_TORCH_INSTALL_EXIT=$LASTEXITCODE"
& $python -c 'import torch;print("CUDA_TORCH",torch.__version__,torch.cuda.is_available())'
$wav=Join-Path $base 'input-16000.wav'
$env:HF_HOME="$root\output\chatgpt\asr-models-hf"
$env:PYTHONIOENCODING='utf-8'
foreach($id in @('c1tech','buzz','cv17','qwen')){
 Write-Output "GPU_RUN $id $(Get-Date -Format o)"
 & $python "$root\scripts\run-persian-asr-matrix.py" --model $id --device cuda --audio $wav --output $base
 Write-Output "GPU_END $id EXIT=$LASTEXITCODE $(Get-Date -Format o)"
}
Write-Output "GPU_PHASE_FINISHED"
