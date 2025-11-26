# Activation script for the virtual environment
cd "C:\AI Agents\CortexMetaAgent\mcp-servers\mcp-tokenstats"
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".venv\Scripts\Activate.ps1"
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "❌ Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    & ".venv\Scripts\Activate.ps1"
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    Write-Host "✅ Virtual environment created and activated" -ForegroundColor Green
}
Write-Host "Python: $(python --version)" -ForegroundColor Cyan
Write-Host "Working directory: $(Get-Location)" -ForegroundColor Cyan

