<# Schedules the token usage graph update every Monday morning. #>

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path (Split-Path (& python -c "import sys; print(sys.executable)")) "pythonw.exe"

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "`"$repo\scripts\update_token_card.py`" --push" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable

Register-ScheduledTask -TaskName "Update GitHub token graph" -Action $action `
    -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Output "Registered 'Update GitHub token graph' using $python"
