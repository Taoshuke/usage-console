# Collects fresh usage, rebuilds the page and deploys it with wrangler (Windows).
# Run by the scheduled task that schedule.ps1 registers; can also be run by hand.
# Unattended deploys read CLOUDFLARE_API_TOKEN (Workers Scripts: Edit) from the user environment.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ('deploy-{0:yyyy-MM}.log' -f (Get-Date))

function Write-Log($text) { "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $text | Tee-Object -FilePath $log -Append }

Set-Location $root
Write-Log 'start'
try {
    foreach ($step in @('collector/collect.py', 'scripts/build.py')) {
        $out = & python -I $step 2>&1
        if ($LASTEXITCODE -ne 0) { throw "$step exited $LASTEXITCODE`n$($out -join "`n")" }
        Write-Log "${step}: $($out -join ' | ')"
    }
    # A scheduled run has no terminal to answer wrangler's prompts, so keep it non-interactive.
    $env:CI = '1'
    $out = & npx --no-install wrangler deploy 2>&1
    if ($LASTEXITCODE -ne 0) { throw "wrangler deploy exited $LASTEXITCODE`n$($out -join "`n")" }
    Write-Log ('deploy: ' + (($out | Select-String -Pattern 'Current Version ID|Deployed|Uploaded') -join ' | '))
    Write-Log 'done'
}
catch {
    Write-Log "FAILED: $_"
    exit 1
}
