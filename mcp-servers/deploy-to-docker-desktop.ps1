<#
.SYNOPSIS
    Deploys MCP servers to Windows Docker Desktop

.DESCRIPTION
    This script builds and deploys all MCP server Docker images to Windows Docker Desktop.
    It checks prerequisites, builds images, and starts containers using docker-compose.

.PARAMETER BuildOnly
    Only build the images without starting containers

.PARAMETER StartOnly
    Only start containers without rebuilding images

.PARAMETER Service
    Deploy only a specific service (mcp-tokenstats, mcp-agent-inventory, mcp-reasoning-cost)

.PARAMETER Stop
    Stop all running containers

.PARAMETER Remove
    Stop and remove all containers and images

.EXAMPLE
    .\deploy-to-docker-desktop.ps1
    Builds and starts all services

.EXAMPLE
    .\deploy-to-docker-desktop.ps1 -BuildOnly
    Only builds the images

.EXAMPLE
    .\deploy-to-docker-desktop.ps1 -Service mcp-tokenstats
    Deploys only the mcp-tokenstats service

.EXAMPLE
    .\deploy-to-docker-desktop.ps1 -Stop
    Stops all running containers

.EXAMPLE
    .\deploy-to-docker-desktop.ps1 -Remove
    Stops and removes all containers and images
#>

param(
    [switch]$BuildOnly,
    [switch]$StartOnly,
    [string]$Service = "",
    [switch]$Stop,
    [switch]$Remove
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MCP Servers Docker Desktop Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if Docker is running
function Test-DockerRunning {
    try {
        $dockerVersion = docker version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Docker is not running or not installed." -ForegroundColor Red
            Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
            return $false
        }
        Write-Host "Docker is running" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "ERROR: Docker is not running or not installed." -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
        return $false
    }
}

# Function to check if docker-compose is available
function Test-DockerCompose {
    try {
        $composeVersion = docker compose version 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: docker-compose is not available." -ForegroundColor Red
            return $false
        }
        Write-Host "Docker Compose is available" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "ERROR: docker-compose is not available." -ForegroundColor Red
        return $false
    }
}

# Function to check required environment variables
function Test-EnvironmentVariables {
    $missing = @()
    
    # Check for mcp-tokenstats
    if ($Service -eq "" -or $Service -eq "mcp-tokenstats") {
        if (-not $env:GOOGLE_API_KEY) {
            $missing += "GOOGLE_API_KEY (required for mcp-tokenstats)"
        }
    }
    
    # Check for mcp-agent-inventory
    if ($Service -eq "" -or $Service -eq "mcp-agent-inventory") {
        if (-not $env:GOOGLE_CLOUD_PROJECT) {
            $missing += "GOOGLE_CLOUD_PROJECT (required for mcp-agent-inventory)"
        }
        if (-not $env:GCP_PROJECT_NUMBER) {
            $missing += "GCP_PROJECT_NUMBER (required for mcp-agent-inventory)"
        }
        
        # Check for credentials file
        $credPath = Join-Path $ScriptDir "mcp-agent-inventory\aiagent-capstoneproject-10beb4eeaf31.json"
        if (-not (Test-Path $credPath)) {
            Write-Host "WARNING: Credentials file not found: $credPath" -ForegroundColor Yellow
            Write-Host "         mcp-agent-inventory may not work without credentials." -ForegroundColor Yellow
        }
    }
    
    if ($missing.Count -gt 0) {
        Write-Host ""
        Write-Host "WARNING: Missing environment variables:" -ForegroundColor Yellow
        foreach ($var in $missing) {
            Write-Host "  - $var" -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "You can set them in PowerShell:" -ForegroundColor Yellow
        Write-Host "  `$env:GOOGLE_API_KEY = 'your-key'" -ForegroundColor Gray
        Write-Host "  `$env:GOOGLE_CLOUD_PROJECT = 'your-project-id'" -ForegroundColor Gray
        Write-Host ""
        $response = Read-Host "Continue anyway? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            return $false
        }
    }
    
    return $true
}

# Handle Stop option
if ($Stop) {
    Write-Host "Stopping all MCP server containers..." -ForegroundColor Yellow
    docker compose down
    if ($LASTEXITCODE -eq 0) {
        Write-Host "All containers stopped" -ForegroundColor Green
    }
    exit 0
}

# Handle Remove option
if ($Remove) {
    Write-Host "Removing all MCP server containers and images..." -ForegroundColor Yellow
    $response = Read-Host "This will remove all containers and images. Continue? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        docker compose down -v --rmi all
        if ($LASTEXITCODE -eq 0) {
            Write-Host "All containers and images removed" -ForegroundColor Green
        }
    }
    exit 0
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Cyan
if (-not (Test-DockerRunning)) {
    exit 1
}
if (-not (Test-DockerCompose)) {
    exit 1
}

Write-Host ""

# Check environment variables
if (-not (Test-EnvironmentVariables)) {
    exit 1
}

Write-Host ""

# Build images
if (-not $StartOnly) {
    Write-Host "Building Docker images..." -ForegroundColor Cyan
    Write-Host ""
    
    if ($Service -ne "") {
        Write-Host "Building $Service..." -ForegroundColor Yellow
        docker compose build $Service
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to build $Service" -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "Building all services..." -ForegroundColor Yellow
        docker compose build
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to build images" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host ""
    Write-Host "Images built successfully" -ForegroundColor Green
    Write-Host ""
}

# Start containers
if (-not $BuildOnly) {
    Write-Host "Starting containers..." -ForegroundColor Cyan
    Write-Host ""
    
    if ($Service -ne "") {
        Write-Host "Starting $Service..." -ForegroundColor Yellow
        docker compose up -d $Service
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to start $Service" -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "Starting all services..." -ForegroundColor Yellow
        docker compose up -d
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to start containers" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host ""
    Write-Host "Containers started successfully" -ForegroundColor Green
    Write-Host ""
    
    # Wait a moment for containers to start
    Start-Sleep -Seconds 3
    
    # Show container status
    Write-Host "Container Status:" -ForegroundColor Cyan
    Write-Host ""
    docker compose ps
    Write-Host ""
    
    # Show service URLs
    Write-Host "Service URLs:" -ForegroundColor Cyan
    Write-Host "  - mcp-tokenstats:      http://localhost:8000" -ForegroundColor Green
    Write-Host "  - mcp-agent-inventory: http://localhost:8001" -ForegroundColor Green
    Write-Host "  - mcp-reasoning-cost:  http://localhost:8002" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Health Check Endpoints:" -ForegroundColor Cyan
    Write-Host "  - http://localhost:8000/health" -ForegroundColor Gray
    Write-Host "  - http://localhost:8001/health" -ForegroundColor Gray
    Write-Host "  - http://localhost:8002/health" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "To view logs:" -ForegroundColor Cyan
    Write-Host "  docker compose logs -f" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To stop containers:" -ForegroundColor Cyan
    Write-Host "  .\deploy-to-docker-desktop.ps1 -Stop" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
