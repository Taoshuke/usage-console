# Sets when tokenboard collects and redeploys (Windows Task Scheduler).
#   .\schedule.ps1 -At 21:30            daily at 21:30
#   .\schedule.ps1 -At 08:00,20:00      twice a day
#   .\schedule.ps1                      show the current schedule
#   .\schedule.ps1 -Remove              stop scheduled updates
param(
    [string[]]$At,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$taskName = 'tokenboard update'

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Output "Removed scheduled task '$taskName'"
    return
}

if (-not $At) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Output 'No schedule yet. Set one with -At 21:30'; return }
    $times = $task.Triggers | ForEach-Object { ([datetime]$_.StartBoundary).ToString('HH:mm') }
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Output ("Daily at {0}; last run {1} (result {2}); next run {3}" -f ($times -join ', '), $info.LastRunTime, $info.LastTaskResult, $info.NextRunTime)
    return
}

$triggers = foreach ($t in $At) {
    $time = [datetime]::ParseExact($t, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
    New-ScheduledTaskTrigger -Daily -At $time
}
$script = Join-Path $PSScriptRoot 'deploy.ps1'
$action = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -File `"$script`""
# A run missed while the computer was off or asleep starts as soon as it is available again.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings `
    -Description 'Collect AI usage and redeploy the tokenboard dashboard' -Force | Out-Null
Write-Output ("Scheduled daily at {0}" -f ($At -join ', '))
