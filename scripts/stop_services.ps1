# Stop PermitOS API, web dev server, and Band agents (no windows)
$root = (Get-Item $PSScriptRoot).Parent.FullName

foreach ($port in @(8000, 5173)) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'permitos|uvicorn api\.main|agents\.(conductor|jurisdiction|building|site_environmental|packager)' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -match 'permitos\\web|vite' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "Stopped PermitOS services."
