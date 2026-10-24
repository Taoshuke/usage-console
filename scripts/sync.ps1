# Collects fresh usage and writes it to Notion (storage "notion"); the site picks it up without a deploy.
# Run by the scheduled task that schedule.ps1 registers. Needs the user environment variable NOTION_TOKEN.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ('sync-{0:yyyy-MM}.log' -f (Get-Date))

function Write-Log($text) { "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $text | Tee-Object -FilePath $log -Append }

Set-Location $root
Write-Log 'start'
$out = & python -I collector/collect.py 2>&1
if ($LASTEXITCODE -ne 0) { Write-Log "FAILED: collect.py exited $LASTEXITCODE`n$($out -join "`n")"; exit 1 }
Write-Log ($out -join ' | ')
Write-Log 'done'
