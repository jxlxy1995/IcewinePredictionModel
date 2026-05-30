$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = "src"
& "C:\ProgramData\anaconda3\python.exe" -m uvicorn icewine_web:app --host 127.0.0.1 --port 8000
