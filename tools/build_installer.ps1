# Giperion/tools/build_installer.ps1                                 v001
# Build a PyInstaller folder (Windows).
# Run: powershell -ExecutionPolicy Bypass -File tools/build_installer.ps1

param(
    [string]$Name = "Giperion",
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller is not installed: python -m pip install pyinstaller"
    exit 1
}

$mode = if ($OneFile) { "--onefile" } else { "--onedir" }

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    $mode,
    "--name", "$Name",
    "--add-data", "skins;skins",
    "--add-data", "knowledge;knowledge",
    "--add-data", "docs;docs",
    "--collect-submodules", "terminal",
    "--collect-submodules", "giperion",
    "main.py"
)

Write-Host ("Build: " + ($arguments -join " "))
& python @arguments

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Done: dist\$Name"
Write-Host "torch and PySide6 are not bundled; this is a Python-machine build."
Write-Host "A clean distribution needs a separate spec with dependencies."
