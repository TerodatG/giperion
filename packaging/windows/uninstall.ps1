# Giperion/packaging/windows/uninstall.ps1                            v001
# Удаление установки из LocalAppData и ярлыка.
# Usage: powershell -ExecutionPolicy Bypass -File uninstall.ps1

param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Giperion")
)

$ErrorActionPreference = "Stop"
$shortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Giperion.lnk"

if (Test-Path $shortcut) {
    Remove-Item $shortcut -Force
}

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
    Write-Host "Удалено: $InstallDir"
} else {
    Write-Host "Не найдено: $InstallDir"
}
