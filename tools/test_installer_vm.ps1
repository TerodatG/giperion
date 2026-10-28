# Giperion/tools/test_installer_vm.ps1                                v002
# Проверка установщика Giperion на чистой Windows в VirtualBox.
#
# Что делает:
#   1. создаёт VM (UEFI + TPM 2.0 — требования Windows 11);
#   2. ставит Windows автоматически (VBoxManage unattended install);
#   3. ждёт Guest Additions;
#   4. копирует установщик, ставит его молча (без прав администратора);
#   5. проверяет файлы, ярлык, запуск приложения и удаление.
#
# Требуется: VirtualBox 7.x и ISO Windows 11 (x64).
#
# Пример:
#   powershell -ExecutionPolicy Bypass -File tools\test_installer_vm.ps1 `
#       -Iso D:\vm\Win11LTSC.iso `
#       -Installer dist\Giperion-1.0.0-windows-x64-setup.exe

param(
    [Parameter(Mandatory = $true)][string]$Iso,
    [Parameter(Mandatory = $true)][string]$Installer,
    [string]$VmName = "Giperion-Win11",
    [string]$VmDir = "D:\vm",
    [string]$User = "giperion",
    [string]$Password = "Giperion!2026",
    [int]$MemoryMB = 6144,
    [int]$Cpus = 4,
    [int]$DiskGB = 65536,
    [string]$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    [switch]$Reuse
)

$ErrorActionPreference = "Stop"

function Step([string]$Text) {
    Write-Host ""
    Write-Host "== $Text" -ForegroundColor Cyan
}

function Fail([string]$Text) {
    Write-Host "FAIL: $Text" -ForegroundColor Red
    exit 1
}

function VBox([string[]]$Args) {
    & $VBoxManage @Args 2>&1
}

function Guest([string[]]$Args) {
    & $VBoxManage guestcontrol $VmName @Args `
        --username $User --password $Password 2>&1
}

function GuestCmd([string]$Command, [int]$TimeoutMs = 600000) {
    Guest @("run", "--exe", "C:\\Windows\\System32\\cmd.exe",
        "--wait-stdout", "--timeout", "$TimeoutMs", "--", "/c", $Command)
}

$Iso = (Resolve-Path $Iso).Path
$Installer = (Resolve-Path $Installer).Path
$installerName = Split-Path $Installer -Leaf
$guestDownloads = "C:\\Users\\$User\\Downloads"

if (-not (Test-Path $VBoxManage)) { Fail "не найден VBoxManage: $VBoxManage" }

Step "VM $VmName"
$existing = (VBox @("list", "vms")) -join "`n"

if ($existing -match [regex]::Escape("`"$VmName`"")) {
    if (-not $Reuse) { Fail "VM уже существует; укажите -Reuse или другое имя" }
} else {
    VBox @("createvm", "--name", $VmName, "--ostype", "Windows11_64",
        "--basefolder", $VmDir, "--register")
    VBox @("modifyvm", $VmName, "--memory", "$MemoryMB", "--cpus", "$Cpus",
        "--vram", "128", "--graphicscontroller", "vboxsvga",
        "--firmware", "efi", "--tpm-type", "2.0", "--nic1", "nat",
        "--audio-enabled", "off")
    VBox @("createmedium", "disk", "--filename", "$VmDir\$VmName\disk.vdi",
        "--size", "$DiskGB", "--format", "VDI")
    VBox @("storagectl", $VmName, "--name", "SATA", "--add", "sata",
        "--controller", "IntelAhci", "--portcount", "2", "--bootable", "on")
    VBox @("storageattach", $VmName, "--storagectl", "SATA", "--port", "0",
        "--device", "0", "--type", "hdd", "--medium", "$VmDir\$VmName\disk.vdi")

    Step "Установка Windows"
    VBox @("unattended", "install", $VmName,
        "--iso=$Iso", "--user=$User", "--password=$Password",
        "--full-user-name=Giperion Test",
        "--locale=en_US", "--country=US", "--time-zone=UTC",
        "--image-index=1", "--install-additions")

    # Запуск отдельным процессом: VM переживает завершение этого скрипта.
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = "`"$VBoxManage`" startvm `"$VmName`" --type headless"
    } | Out-Null
}

Step "Ожидание Guest Additions"
$deadline = (Get-Date).AddMinutes(60)
$ready = $false

while ((Get-Date) -lt $deadline) {
    $ip = (VBox @("guestproperty", "get", $VmName,
        "/VirtualBox/GuestInfo/Net/0/V4/IP")) -join " "

    if ($ip -match "Value: \d") { $ready = $true; break }

    Start-Sleep -Seconds 20
}

if (-not $ready) { Fail "гость не поднялся за 60 минут" }

Step "Копирование установщика"
Guest @("copyto", $Installer, "$guestDownloads\\$installerName")

Step "Установка (без администратора)"
$result = GuestCmd "$guestDownloads\\$installerName /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=$guestDownloads\\install.log & echo EXITCODE=%ERRORLEVEL%" 1800000
$result | Out-Host

Step "Проверка файлов и ярлыка"
$check = GuestCmd 'if exist "%LOCALAPPDATA%\Programs\Giperion\Giperion.exe" (echo EXE_OK) else (echo EXE_MISSING)'
$check | Out-Host

$check = GuestCmd 'if exist "%LOCALAPPDATA%\Programs\Giperion\_internal\models\seq2seq.pt" (echo MODELS_OK) else (echo MODELS_MISSING)'
$check | Out-Host

$check = GuestCmd 'if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Giperion" (echo LNK_OK) else (echo LNK_MISSING)'
$check | Out-Host

Step "Запуск приложения"
Guest @("start", "--exe", "C:\\Users\\$User\\AppData\\Local\\Programs\\Giperion\\Giperion.exe") | Out-Null
Start-Sleep -Seconds 40
$running = GuestCmd 'tasklist | findstr /i giperion.exe'
$running | Out-Host

Step "Удаление"
GuestCmd 'taskkill /IM Giperion.exe /F' | Out-Null
GuestCmd '"%LOCALAPPDATA%\Programs\Giperion\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART' 600000 | Out-Null
Start-Sleep -Seconds 10

$left = GuestCmd 'if exist "%LOCALAPPDATA%\Programs\Giperion" (echo DIR_LEFT) else (echo DIR_GONE)'
$left | Out-Host

Step "Готово"
Write-Host "Ожидается: EXITCODE=0, EXE_OK, LNK_OK, процесс Giperion.exe, DIR_GONE."
