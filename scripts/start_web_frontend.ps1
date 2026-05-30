$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "web"
Set-Location $webRoot

if (-not (Test-Path "node_modules")) {
    npm install
}

$env:VITE_API_BASE_URL = ""
npm run dev -- --host 127.0.0.1 --port 5173
