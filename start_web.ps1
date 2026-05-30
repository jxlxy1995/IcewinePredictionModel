param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"

$BackendPort = 8000
$FrontendPort = 5173
$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendScript = Join-Path $repoRoot "scripts\start_web_api.ps1"
$frontendScript = Join-Path $repoRoot "scripts\start_web_frontend.ps1"
$stateDir = Join-Path $repoRoot ".web"
$backendPidFile = Join-Path $stateDir "backend.pid"
$frontendPidFile = Join-Path $stateDir "frontend.pid"

function Get-ListeningProcessIds {
    param([int]$Port)

    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -gt 0 })
}

function Write-PortStatus {
    param(
        [string]$Name,
        [int]$Port,
        [string]$Url
    )

    $processIds = Get-ListeningProcessIds -Port $Port
    if ($processIds.Count -eq 0) {
        Write-Host "$Name stopped  $Url"
        return
    }

    Write-Host "$Name running  $Url  PID=$($processIds -join ',')"
}

function Wait-PortState {
    param(
        [int]$Port,
        [bool]$ShouldListen,
        [int]$TimeoutSeconds = 12
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $isListening = (Get-ListeningProcessIds -Port $Port).Count -gt 0
        if ($isListening -eq $ShouldListen) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Save-ManagedPid {
    param(
        [string]$PidFile,
        [int]$ProcessId
    )

    if (-not (Test-Path $stateDir)) {
        New-Item -ItemType Directory -Path $stateDir | Out-Null
    }
    Set-Content -Path $PidFile -Value $ProcessId -Encoding ASCII
}

function Get-ManagedPid {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return @()
    }

    $rawValue = (Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $processId = 0
    if ([int]::TryParse($rawValue, [ref]$processId) -and $processId -gt 0) {
        return @($processId)
    }
    return @()
}

function Remove-ManagedPid {
    param([string]$PidFile)

    if (Test-Path $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
}

function Get-ProcessInfo {
    param([int]$ProcessId)

    Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Test-CommandLineMatch {
    param(
        [string]$CommandLine,
        [string[]]$MarkerPatterns
    )

    foreach ($pattern in $MarkerPatterns) {
        if ($CommandLine -like "*$pattern*") {
            return $true
        }
    }
    return $false
}

function Get-ChildProcessIds {
    param([int]$ParentProcessId)

    @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentProcessId" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty ProcessId)
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    foreach ($childProcessId in Get-ChildProcessIds -ParentProcessId $ProcessId) {
        Stop-ProcessTree -ProcessId $childProcessId
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Get-RelatedRootProcessIds {
    param(
        [int]$ProcessId,
        [string[]]$MarkerPatterns
    )

    $roots = New-Object System.Collections.Generic.List[int]
    $currentProcessId = $ProcessId
    $lastMatchingProcessId = $ProcessId

    while ($currentProcessId -gt 0) {
        $processInfo = Get-ProcessInfo -ProcessId $currentProcessId
        if ($null -eq $processInfo) {
            break
        }

        $commandLine = [string]$processInfo.CommandLine
        if (Test-CommandLineMatch -CommandLine $commandLine -MarkerPatterns $MarkerPatterns) {
            $lastMatchingProcessId = [int]$processInfo.ProcessId
            $currentProcessId = [int]$processInfo.ParentProcessId
            continue
        }

        break
    }

    $roots.Add($lastMatchingProcessId)
    return @($roots | Select-Object -Unique)
}

function Start-WebProcess {
    param(
        [string]$Name,
        [int]$Port,
        [string]$ScriptPath,
        [string]$Url,
        [string]$PidFile
    )

    $processIds = Get-ListeningProcessIds -Port $Port
    if ($processIds.Count -gt 0) {
        Write-Host "$Name already running  $Url  PID=$($processIds -join ',')"
        return
    }

    $process = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ScriptPath
    )
    Save-ManagedPid -PidFile $PidFile -ProcessId $process.Id
    Write-Host "$Name starting  $Url  launcher PID=$($process.Id)"
    if (-not (Wait-PortState -Port $Port -ShouldListen $true)) {
        Write-Host "$Name start requested, but port $Port is not listening yet"
    }
}

function Stop-WebProcess {
    param(
        [string]$Name,
        [int]$Port,
        [string]$PidFile,
        [string[]]$MarkerPatterns
    )

    $seedProcessIds = @()
    $seedProcessIds += Get-ManagedPid -PidFile $PidFile
    $seedProcessIds += Get-ListeningProcessIds -Port $Port
    $seedProcessIds = @($seedProcessIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)

    if ($seedProcessIds.Count -eq 0) {
        Write-Host "$Name already stopped"
        Remove-ManagedPid -PidFile $PidFile
        return
    }

    $processIds = @()
    foreach ($seedProcessId in $seedProcessIds) {
        $processIds += Get-RelatedRootProcessIds -ProcessId $seedProcessId -MarkerPatterns $MarkerPatterns
    }
    $processIds = @($processIds | Select-Object -Unique)

    foreach ($processId in $processIds) {
        Write-Host "$Name stopping  PID=$processId"
        Stop-ProcessTree -ProcessId $processId
    }
    Remove-ManagedPid -PidFile $PidFile
    if (-not (Wait-PortState -Port $Port -ShouldListen $false)) {
        Write-Host "$Name stop requested, but port $Port is still listening"
    }
}

function Start-Web {
    Start-WebProcess -Name "Backend " -Port $BackendPort -ScriptPath $backendScript -Url $BackendUrl -PidFile $backendPidFile
    Start-WebProcess -Name "Frontend" -Port $FrontendPort -ScriptPath $frontendScript -Url $FrontendUrl -PidFile $frontendPidFile
    Write-Host ""
    Write-PortStatus -Name "Backend " -Port $BackendPort -Url $BackendUrl
    Write-PortStatus -Name "Frontend" -Port $FrontendPort -Url $FrontendUrl
}

function Stop-Web {
    Stop-WebProcess `
        -Name "Frontend" `
        -Port $FrontendPort `
        -PidFile $frontendPidFile `
        -MarkerPatterns @($frontendScript, "npm run dev", "vite")
    Stop-WebProcess `
        -Name "Backend " `
        -Port $BackendPort `
        -PidFile $backendPidFile `
        -MarkerPatterns @($backendScript, "icewine_web:app", "uvicorn")
}

function Show-WebStatus {
    Write-PortStatus -Name "Backend " -Port $BackendPort -Url $BackendUrl
    Write-PortStatus -Name "Frontend" -Port $FrontendPort -Url $FrontendUrl
}

switch ($Action) {
    "start" {
        Start-Web
    }
    "stop" {
        Stop-Web
        Show-WebStatus
    }
    "restart" {
        Stop-Web
        Start-Sleep -Seconds 1
        Start-Web
    }
    "status" {
        Show-WebStatus
    }
}
