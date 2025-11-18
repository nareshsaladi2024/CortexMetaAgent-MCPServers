# PowerShell script to run the ReasoningCost MCP Server
# This avoids Windows popup asking which program to use

# Navigate to script directory
Set-Location $PSScriptRoot

Write-Host "Starting ReasoningCost MCP Server..." -ForegroundColor Green
Write-Host ("=" * 50) -ForegroundColor Gray
Write-Host ""

# Check for port configuration
if (-not $env:PORT) {
    $env:PORT = 8002
    Write-Host "Using default port: 8002" -ForegroundColor Cyan
    Write-Host "Set `$env:PORT to use a different port" -ForegroundColor Gray
    Write-Host ""
}

# Find Python executable (use actual .exe file, not Windows redirect)
$python = $null

# Try to get real Python executable by running where.exe
$wherePython = where.exe python 2>$null | Where-Object { $_ -match "\.exe$" } | Select-Object -First 1
if ($wherePython -and (Test-Path $wherePython)) {
    $python = $wherePython
} elseif (Test-Path "c:\ProgramData\anaconda3\python.exe") {
    $python = "c:\ProgramData\anaconda3\python.exe"
} elseif (Test-Path "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe") {
    $python = (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" | Select-Object -First 1).FullName
} else {
    $python = "python"
}

Write-Host "Python: $python" -ForegroundColor Cyan
Write-Host "Directory: $PSScriptRoot" -ForegroundColor Cyan
Write-Host "Port: $env:PORT" -ForegroundColor Cyan
Write-Host ""

# Run the server
Write-Host "Starting server on http://localhost:$env:PORT" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Use explicit Python executable with full path to avoid Windows popup
if ($python -match "\.exe$") {
    # Already has .exe extension
    & $python server.py
} elseif (Test-Path "$python.exe") {
    # Add .exe if it exists
    & "$python.exe" server.py
} else {
    # Use as-is (should work if in PATH)
    & $python server.py
}

