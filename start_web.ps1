$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendScript = Join-Path $repoRoot "scripts\start_web_api.ps1"
$frontendScript = Join-Path $repoRoot "scripts\start_web_frontend.ps1"

$backendProcess = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $backendScript
)

Write-Host "Backend:  http://127.0.0.1:8000  PID=$($backendProcess.Id)"
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Stop backend later with: Stop-Process -Id $($backendProcess.Id)"

& $frontendScript
