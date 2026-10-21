$ErrorActionPreference='Stop'
$repo='C:\GitHub\yt-dlp'
$env:HF_HOME=Join-Path $repo 'output\chatgpt\asr-models-hf'
$hf=Join-Path $repo 'output\chatgpt\asr-comparison-venv\Scripts\hf.exe'
Write-Host 'C1Tech Small requires a Hugging Face READ access token authorized for C1Tech/whisper_small_persian.'
Write-Host 'Create the READ token at https://huggingface.co/settings/tokens under the same account that accepted the model owner terms.'
Write-Host 'Paste the token into the upcoming LOCAL PowerShell prompt, NOT into ChatGPT. It is not added to Git credentials.'
& $hf auth login
if($LASTEXITCODE -ne 0){throw 'Local Hugging Face sign-in failed'}
Write-Host 'Local Hugging Face sign-in finished. The background GPU benchmark will start after access is verified.'
