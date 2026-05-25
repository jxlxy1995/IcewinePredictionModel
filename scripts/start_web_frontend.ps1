$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "web"
Set-Location $webRoot

if (-not (Test-Path "node_modules")) {
    npm install
}

npm run dev
