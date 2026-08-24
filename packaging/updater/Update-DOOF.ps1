# DOOF Windows update helper (PowerShell)
# Invoked by the staged update after DOOF exits.
param(
  [Parameter(Mandatory = $true)][string]$PendingJson,
  [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
$pending = Get-Content -Raw -Path $PendingJson | ConvertFrom-Json
$extract = $pending.extract
if (-not (Test-Path $extract)) { Write-Error "Extract missing"; exit 1 }

if (-not $InstallDir) {
  $InstallDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  if (-not (Test-Path (Join-Path $InstallDir "DOOF.exe"))) {
    $InstallDir = Split-Path -Parent $InstallDir
  }
}

$exe = Join-Path $InstallDir "DOOF.exe"
# Wait for lock release
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
  try {
    $fs = [System.IO.File]::Open($exe, 'Open', 'ReadWrite', 'None')
    $fs.Close()
    break
  } catch { Start-Sleep -Milliseconds 500 }
}

$backup = Join-Path (Split-Path $InstallDir) "DOOF_backup"
if (Test-Path $backup) { Remove-Item -Recurse -Force $backup }
Copy-Item -Recurse -Force $InstallDir $backup

$src = Join-Path $extract "DOOF"
if (-not (Test-Path $src)) { $src = $extract }
Copy-Item -Recurse -Force (Join-Path $src "*") $InstallDir

$done = [IO.Path]::ChangeExtension($PendingJson, ".done.json")
Move-Item -Force $PendingJson $done

if (Test-Path $exe) { Start-Process -FilePath $exe -WorkingDirectory $InstallDir }
Write-Host "DOOF update complete: $($pending.version)"
