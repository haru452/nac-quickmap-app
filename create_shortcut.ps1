# Creates a "NAC QuickMap" shortcut on the Desktop.
# Place this file in the same folder as main.py.
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $py)) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { Write-Host "pythonw.exe was not found. Is Python installed?"; exit 1 }
    $py = $cmd.Source
}

$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desktop "NAC QuickMap.lnk"))
$lnk.TargetPath = $py
$lnk.Arguments = '"' + (Join-Path $root "main.py") + '"'
$lnk.WorkingDirectory = $root
$icon = Join-Path $root "icon.ico"
if (Test-Path $icon) { $lnk.IconLocation = $icon }
$lnk.Save()
Write-Host "Shortcut created on the Desktop."
