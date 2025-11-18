# PowerShell script to run the AgentInventory MCP Server
# This avoids Windows popup asking which program to use

# Navigate to script directory
Set-Location $PSScriptRoot

# Load environment variables from .env file if it exists
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)\s*$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            if ($value -match '^["''](.*)["'']$') {
                $value = $matches[1]
            }
            
            # Resolve relative paths for GOOGLE_APPLICATION_CREDENTIALS
            if ($key -eq "GOOGLE_APPLICATION_CREDENTIALS" -and $value) {
                if (-not [System.IO.Path]::IsPathRooted($value)) {
                    # Path is relative, resolve it relative to .env file location
                    $resolvedPath = Join-Path $PSScriptRoot $value
                    $resolvedPath = [System.IO.Path]::GetFullPath($resolvedPath)
                    if (Test-Path $resolvedPath) {
                        $value = $resolvedPath
                        Write-Host "  Resolved relative path to: $value" -ForegroundColor Gray
                    } else {
                        Write-Host "  Warning: GOOGLE_APPLICATION_CREDENTIALS path not found: $resolvedPath" -ForegroundColor Yellow
                    }
                }
            }
            
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
            Write-Host "  Loaded: $key" -ForegroundColor Gray
        }
    }
    Write-Host ""
}

Write-Host "Starting AgentInventory MCP Server..." -ForegroundColor Green
Write-Host ("=" * 50) -ForegroundColor Gray
Write-Host ""

# Check for port configuration
if (-not $env:PORT) {
    $env:PORT = 8001
    Write-Host "Using default port: 8001" -ForegroundColor Cyan
    Write-Host "Set `$env:PORT to use a different port" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "Using port from .env: $env:PORT" -ForegroundColor Cyan
    Write-Host ""
}

# Display GCP configuration if set
if ($env:GCP_PROJECT_ID) {
    Write-Host "GCP Configuration:" -ForegroundColor Cyan
    Write-Host "  Project ID: $env:GCP_PROJECT_ID" -ForegroundColor White
    Write-Host "  Location: $(if ($env:GCP_LOCATION) { $env:GCP_LOCATION } else { 'us-central1 (default)' })" -ForegroundColor White
    Write-Host "  Reasoning Engine Location: global (required by API)" -ForegroundColor White
    if ($env:GOOGLE_APPLICATION_CREDENTIALS) {
        if (Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS) {
            Write-Host "  Credentials: $env:GOOGLE_APPLICATION_CREDENTIALS" -ForegroundColor Green
            Write-Host "    [OK] Service account file found" -ForegroundColor Gray
        } else {
            Write-Host "  Credentials: $env:GOOGLE_APPLICATION_CREDENTIALS" -ForegroundColor Red
            Write-Host "    [ERROR] Service account file NOT found!" -ForegroundColor Red
        }
    } else {
        Write-Host "  Credentials: Not set (using default GCP authentication)" -ForegroundColor Yellow
        Write-Host "    Set GOOGLE_APPLICATION_CREDENTIALS in .env for service account auth" -ForegroundColor Gray
    }
    Write-Host ""
} else {
    Write-Host "GCP Configuration: Not set (MCP Reasoning Engine endpoints will not work)" -ForegroundColor Yellow
    Write-Host "  Add GCP_PROJECT_ID to .env file to enable GCP features" -ForegroundColor Gray
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
    $pythonExe = "$python.exe"
    & $pythonExe server.py
} else {
    # Use as-is (should work if in PATH)
    & $python server.py
}

