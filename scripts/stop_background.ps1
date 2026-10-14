# Stop the background jobs before moving / shutting down the laptop.
#   - depth recorder: graceful (STOP file -> final flush, waits up to 30 s)
#   - research: killed; finished jobs are already cached in data/research/t18 and are
#     skipped on the next start (only jobs in progress are recomputed)
# Usage (from D:\Scalping):  powershell -ExecutionPolicy Bypass -File scripts\stop_background.ps1

$root = Split-Path -Parent $PSScriptRoot

function Get-Running($pattern) {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like "*$pattern*" }
}

$recorder = Get-Running "record_depth.py"
if ($recorder) {
    New-Item -ItemType File -Force (Join-Path $root "data\futures_um\depth\STOP") | Out-Null
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Running "record_depth.py") -and (Get-Date) -lt $deadline) { Start-Sleep 1 }
    if (Get-Running "record_depth.py") {
        Get-Running "record_depth.py" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Write-Output "depth recorder: did not stop in 30 s, killed"
    } else {
        Write-Output "depth recorder: stopped cleanly (buffer flushed)"
    }
} else {
    Write-Output "depth recorder: not running"
}

$research = Get-Running "research_stop_hunt.py"
$workers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*multiprocessing*" }
if ($research -or $workers) {
    @($research) + @($workers) | Where-Object { $_ } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $cached = (Get-ChildItem (Join-Path $root "data\research\t18") -Filter *.pkl -ErrorAction SilentlyContinue).Count
    Write-Output "research: stopped ($cached of 24 jobs cached)"
} else {
    Write-Output "research: not running"
}
