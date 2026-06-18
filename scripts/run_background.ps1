# Start a process with no visible window; stdout/stderr go to logs/
param(
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)][string]$WorkingDirectory,
    [Parameter(Mandatory)][string]$FilePath,
    [Parameter()][string[]]$ArgumentList = @()
)

$root = (Get-Item $PSScriptRoot).Parent.FullName
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$out = Join-Path $logDir "$Name.out.log"
$err = Join-Path $logDir "$Name.err.log"

Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err | Out-Null

Write-Host "Started $Name (logs: logs\$Name.out.log)"
