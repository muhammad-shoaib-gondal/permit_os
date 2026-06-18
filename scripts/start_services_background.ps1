# Start API, web, and Band agents in the background (no PowerShell popups)
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

& (Join-Path $PSScriptRoot "stop_services.ps1")
Start-Sleep -Seconds 2

$run = Join-Path $PSScriptRoot "run_background.ps1"

Write-Host "Starting PermitOS (hidden) - repo: $root"
Write-Host "Logs: $(Join-Path $root 'logs')"

& $run -Name "api" -WorkingDirectory $root -FilePath "python" -ArgumentList @("-m", "uvicorn", "api.main:app", "--port", "8000")
Start-Sleep -Seconds 2

$webDir = Join-Path $root "web"
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory $webDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir "web.out.log") `
    -RedirectStandardError (Join-Path $logDir "web.err.log") | Out-Null
Write-Host "Started web (logs: logs\web.out.log)"

$agents = @(
    "agents.jurisdiction.agent",
    "agents.building.agent",
    "agents.site_environmental.agent",
    "agents.packager.agent"
)
foreach ($a in $agents) {
    & $run -Name ($a -replace '\.', '-') -WorkingDirectory $root -FilePath "python" -ArgumentList @("-m", $a)
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "API:  http://127.0.0.1:8000"
Write-Host "Web:  http://localhost:5173"
Write-Host "Stop: scripts\stop_services.ps1"
