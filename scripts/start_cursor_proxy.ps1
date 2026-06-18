# Start OpenAI-compatible proxy for Cursor Composer (Band agents use ChatOpenAI).
# Requires Node.js 18+ and CURSOR_API_KEY in .env or environment.
$root = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $root

$proxyDir = Join-Path $root "_vendor\cursor-openai-api"
if (-not (Test-Path $proxyDir)) {
    Write-Host "Cloning cursor-openai-api into _vendor..."
    git clone --depth 1 https://github.com/Randomblock1/cursor-openai-api.git $proxyDir
}

# Load .env (simple KEY=VALUE lines)
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            Set-Item -Path "env:$name" -Value $value
        }
    }
}

if (-not $env:CURSOR_API_KEY) {
    Write-Error "Set CURSOR_API_KEY in .env (Cursor Dashboard -> Integrations)."
    exit 1
}

$env:CURSOR_CWD = if ($env:CURSOR_CWD) { $env:CURSOR_CWD } else { $root }
$env:PORT = if ($env:CURSOR_PROXY_PORT) { $env:CURSOR_PROXY_PORT } else { "8787" }
$env:HOST = if ($env:CURSOR_PROXY_HOST) { $env:CURSOR_PROXY_HOST } else { "127.0.0.1" }

Write-Host "Installing proxy dependencies in $proxyDir ..."
Set-Location $proxyDir
npm install --silent 2>$null
# @cursor/sdk peer deps (not always pulled by npm)
npm install --silent @connectrpc/connect-node @connectrpc/connect 2>$null

Write-Host "Starting Cursor Composer proxy on http://$($env:HOST):$($env:PORT)/v1"
Write-Host "Model: composer-2.5 | CWD: $($env:CURSOR_CWD)"
npm run start:node
