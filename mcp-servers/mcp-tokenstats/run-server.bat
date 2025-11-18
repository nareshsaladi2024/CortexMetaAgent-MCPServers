@echo off
REM Batch file to run the TokenStats MCP Server
REM This avoids Windows popup asking which program to use

cd /d "%~dp0"

echo Starting TokenStats MCP Server...
echo.

REM Try to find Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python found
    goto run
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Python3 found
    set python=python3
    goto run
)

echo ERROR: Python not found. Please install Python or add it to PATH.
pause
exit /b 1

:run
echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

python server.py

