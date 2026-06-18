# Start Band agents in the background (no PowerShell popups)
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

Write-Host "Starting Band agents (hidden) - repo: $root"
if ((Get-Content (Join-Path $root ".env") -ErrorAction SilentlyContinue) -match 'LLM_BACKEND=cursor') {
    Write-Host "Cursor mode: run scripts/start_cursor_proxy.ps1 first."
}

$run = Join-Path $PSScriptRoot "run_background.ps1"
$agents = @(
    "agents.conductor.agent",
    "agents.jurisdiction.agent",
    "agents.building.agent",
    "agents.site_environmental.agent",
    "agents.packager.agent"
)

foreach ($a in $agents) {
    & $run -Name ($a -replace '\.', '-') -WorkingDirectory $root -FilePath "python" -ArgumentList @("-m", $a)
    Start-Sleep -Seconds 2
}

Write-Host "Done. Logs: $(Join-Path $root 'logs')"
