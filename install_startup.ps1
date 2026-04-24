# Install JARVIS dependencies and register it to launch at user login.
# Run from the repo root in PowerShell:  .\install_startup.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==> Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r (Join-Path $root "requirements.txt")

$startup  = [Environment]::GetFolderPath("Startup")
$shortcut = Join-Path $startup "JARVIS.lnk"
$vbs      = Join-Path $root "start_jarvis.vbs"

if (-not (Test-Path $vbs)) {
    throw "start_jarvis.vbs not found at $vbs"
}

Write-Host "==> Creating Startup shortcut at $shortcut"
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($shortcut)
$lnk.TargetPath       = "wscript.exe"
$lnk.Arguments        = '"' + $vbs + '"'
$lnk.WorkingDirectory = $root
$lnk.WindowStyle      = 7   # minimized / hidden
$lnk.Description      = "JARVIS clap-triggered automation"
$lnk.Save()

Write-Host "==> Starting JARVIS now..."
Start-Process wscript.exe -ArgumentList ('"' + $vbs + '"')

Write-Host ""
Write-Host "Installed. JARVIS will start automatically at next login."
Write-Host "To remove: delete '$shortcut'."
