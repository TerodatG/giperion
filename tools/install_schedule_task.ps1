# Giperion/tools/install_schedule_task.ps1                             v001
# Регистрирует ежечасный запуск tools.agent_schedule run-due.
# Запускать из корня проекта: powershell -ExecutionPolicy Bypass -File ...

param(
    [string]$TaskName = "GiperionAgentSchedule",
    [int]$EveryMinutes = 60,
    [string]$Python = "python",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false `
        -ErrorAction SilentlyContinue
    Write-Host "Задача удалена:" $TaskName
    exit 0
}

$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "-m tools.agent_schedule run-due --limit 2" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Description "Giperion: read-only задачи по расписанию" `
    -Force | Out-Null

Write-Host "Зарегистрировано:" $TaskName
Write-Host "Каждые $EveryMinutes мин, папка:" $root
Write-Host "Проверить: Get-ScheduledTask -TaskName $TaskName"
Write-Host "Удалить: powershell -File tools/install_schedule_task.ps1 -Remove"
