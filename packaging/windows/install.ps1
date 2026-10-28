# Giperion/packaging/windows/install.ps1                              v001
# Установка без администратора: копирование в LocalAppData + ярлык.
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [string]$Source = (Join-Path $PSScriptRoot "Giperion"),
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Giperion")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $Source "Giperion.exe"))) {
    Write-Host "Нет Giperion.exe в $Source"
    exit 1
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $Source "*") -Destination $InstallDir -Recurse -Force

$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$shortcutPath = Join-Path $startMenu "Giperion.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $InstallDir "Giperion.exe"
$shortcut.WorkingDirectory = $InstallDir
$shortcut.Description = "Giperion"
$shortcut.Save()

Write-Host "Установлено: $InstallDir"
Write-Host "Ярлык: $shortcutPath"
