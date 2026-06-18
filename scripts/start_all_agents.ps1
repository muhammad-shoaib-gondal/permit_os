# Start all 5 PermitOS Band agents (run from repo root after .env is configured)
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

Write-Host "Starting 5 PermitOS agents in separate windows..."
Write-Host "Repo: $root"
Write-Host "Requires: .env with LLM_BACKEND + API key, agent_config.yaml"
if ((Get-Content (Join-Path $root ".env") -ErrorAction SilentlyContinue) -match 'LLM_BACKEND=cursor') {
    Write-Host "Cursor mode: run scripts/start_cursor_proxy.ps1 first (separate window)."
}

$agents = @(
    "agents.conductor.agent",
    "agents.jurisdiction.agent",
    "agents.building.agent",
    "agents.site_environmental.agent",
    "agents.packager.agent"
)

foreach ($a in $agents) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m $a"
    Start-Sleep -Seconds 2
}

Write-Host "Done. Check each window for 'Agent started:' or 'Starting PermitOS' message."
