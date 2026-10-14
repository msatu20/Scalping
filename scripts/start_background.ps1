# Start (or resume) the long-running background jobs, detached from any terminal:
#   - depth recorder (T14): needs internet; reconnects by itself
#   - STOP_HUNT_REBOUND research (T18): resumes from data/research/t18 cache
# Usage (from D:\Scalping):  powershell -ExecutionPolicy Bypass -File scripts\start_background.ps1
# Options: -NoResearch, -NoRecorder, -Workers 10

param([switch]$NoResearch, [switch]$NoRecorder, [int]$Workers = 10)

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null

function Test-Running($pattern) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like "*$pattern*" }
}

if (-not $NoRecorder) {
    if (Test-Running "record_depth.py") {
        Write-Output "depth recorder: already running"
    } else {
        Remove-Item -ErrorAction SilentlyContinue (Join-Path $root "data\futures_um\depth\STOP")
        Start-Process -FilePath $python -ArgumentList "scripts\record_depth.py" `
            -WorkingDirectory $root -WindowStyle Hidden | Out-Null
        Write-Output "depth recorder: started (log: logs\depth_recorder.log)"
    }
}

if (-not $NoResearch) {
    if (Test-Running "research_stop_hunt.py") {
        Write-Output "research: already running"
    } else {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        Start-Process -FilePath $python `
            -ArgumentList "-u", "scripts\research_stop_hunt.py", "--start", "2025-10-13", `
                          "--end", "2026-10-12", "--workers", "$Workers" `
            -WorkingDirectory $root -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $root "logs\research_stop_hunt.log") `
            -RedirectStandardError (Join-Path $root "logs\research_stop_hunt.err.$stamp.log") | Out-Null
        Write-Output "research: started (log: logs\research_stop_hunt.log)"
    }
}
