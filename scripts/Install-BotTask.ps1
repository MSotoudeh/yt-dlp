<#
.SYNOPSIS
  Registers (or repairs) the scheduled task that keeps the private Telegram bot running.

.DESCRIPTION
  Run once from an elevated PowerShell. Safe to re-run: it replaces the task definition.
  The task starts the bot at boot as SYSTEM and restarts it after any exit. The settings below
  fix the failure modes of the previous definition: only 3 restarts (a single network outage
  at boot could leave the bot dead until the next reboot), and "stop on battery".
#>
$ErrorActionPreference = 'Stop'
$taskName = 'YTDLP-Independent-Telegram-Bot'
$script = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'start-telegram-bot.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $script)
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Registered '$taskName'. Start it now with: Start-ScheduledTask -TaskName '$taskName'"
