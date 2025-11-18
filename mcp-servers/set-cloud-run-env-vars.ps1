<#
.SYNOPSIS
    Set environment variables for Cloud Run services

.DESCRIPTION
    This script helps you set environment variables for your Cloud Run MCP services.
    You can either set them from local environment variables or provide them directly.

.PARAMETER Service
    The service name (mcp-tokenstats, mcp-agent-inventory, mcp-reasoning-cost)

.PARAMETER GoogleApiKey
    Google API Key for mcp-tokenstats

.PARAMETER GoogleCloudProject
    Google Cloud Project ID for mcp-agent-inventory

.PARAMETER GcpProjectNumber
    Google Cloud Project Number for mcp-agent-inventory

.PARAMETER GcpLocation
    Google Cloud Location for mcp-agent-inventory (default: us-central1)

.PARAMETER ShowCurrent
    Show current environment variable values for a service

.EXAMPLE
    .\set-cloud-run-env-vars.ps1 -Service mcp-tokenstats -GoogleApiKey "your-api-key"

.EXAMPLE
    # Set from local environment variables
    $env:GOOGLE_API_KEY = "your-api-key"
    .\set-cloud-run-env-vars.ps1 -Service mcp-tokenstats

.EXAMPLE
    # Show current values
    .\set-cloud-run-env-vars.ps1 -Service mcp-tokenstats -ShowCurrent
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("mcp-tokenstats", "mcp-agent-inventory", "mcp-reasoning-cost")]
    [string]$Service = "",
    
    [switch]$ShowCurrent,
    
    [string]$GoogleApiKey = "",
    [string]$GoogleCloudProject = "",
    [string]$GcpProjectNumber = "",
    [string]$GcpLocation = "us-central1"
)

$ErrorActionPreference = "Stop"

$ProjectId = "aiagent-capstoneproject"
$Region = "us-central1"

# Handle ShowCurrent
if ($ShowCurrent) {
    if (-not $Service) {
        Write-Host "ERROR: -Service parameter is required with -ShowCurrent" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Current environment variables for ${Service}:" -ForegroundColor Cyan
    Write-Host ""
    
    try {
        $envVarsJson = gcloud run services describe $Service --region $Region --format="json" --project $ProjectId 2>&1 | ConvertFrom-Json
        
        if ($LASTEXITCODE -eq 0 -and $envVarsJson) {
            $envVars = $envVarsJson.spec.template.spec.containers[0].env
            
            if ($envVars -and $envVars.Count -gt 0) {
                $envVars | ForEach-Object {
                    $name = $_.name
                    $value = $_.value
                    if ($name -eq "GOOGLE_API_KEY" -and $value -and $value.Length -gt 4) {
                        $value = "***" + $value.Substring($value.Length - 4)
                    }
                    Write-Host "  $name = $value" -ForegroundColor Green
                }
            } else {
                Write-Host "  No environment variables set" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  No environment variables set" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  Could not retrieve environment variables" -ForegroundColor Red
        Write-Host "  Error: $_" -ForegroundColor Red
    }
    
    Write-Host ""
    exit 0
}

if (-not $Service) {
    Write-Host "ERROR: -Service parameter is required" -ForegroundColor Red
    Write-Host "Usage: .\set-cloud-run-env-vars.ps1 -Service <service-name> [options]" -ForegroundColor Yellow
    exit 1
}

Write-Host "Setting environment variables for $Service..." -ForegroundColor Cyan
Write-Host ""

# Build environment variable arguments
$envVars = @()

if ($Service -eq "mcp-tokenstats") {
    # Get API key from parameter or environment
    $apiKey = if ($GoogleApiKey) { $GoogleApiKey } else { $env:GOOGLE_API_KEY }
    
    if (-not $apiKey) {
        Write-Host "ERROR: GOOGLE_API_KEY is required for mcp-tokenstats" -ForegroundColor Red
        Write-Host "Set it with: -GoogleApiKey 'your-key' or set `$env:GOOGLE_API_KEY" -ForegroundColor Yellow
        exit 1
    }
    
    $envVars += "GOOGLE_API_KEY=$apiKey"
    Write-Host "Setting GOOGLE_API_KEY" -ForegroundColor Green
}

elseif ($Service -eq "mcp-agent-inventory") {
    # Get values from parameters or environment
    $projectId = if ($GoogleCloudProject) { $GoogleCloudProject } else { $env:GOOGLE_CLOUD_PROJECT }
    $projectNumber = if ($GcpProjectNumber) { $GcpProjectNumber } else { $env:GCP_PROJECT_NUMBER }
    $location = if ($GcpLocation) { $GcpLocation } else { $env:GCP_LOCATION }
    
    if (-not $projectId) {
        Write-Host "WARNING: GOOGLE_CLOUD_PROJECT not set, using default: $ProjectId" -ForegroundColor Yellow
        $projectId = $ProjectId
    }
    
    if (-not $projectNumber) {
        Write-Host "WARNING: GCP_PROJECT_NUMBER not set" -ForegroundColor Yellow
    }
    
    if (-not $location) {
        $location = "us-central1"
    }
    
    $envVars += "GOOGLE_CLOUD_PROJECT=$projectId"
    $envVars += "GCP_PROJECT_NUMBER=$projectNumber"
    $envVars += "GCP_LOCATION=$location"
    
    Write-Host "Setting GOOGLE_CLOUD_PROJECT=$projectId" -ForegroundColor Green
    Write-Host "Setting GCP_PROJECT_NUMBER=$projectNumber" -ForegroundColor Green
    Write-Host "Setting GCP_LOCATION=$location" -ForegroundColor Green
}

elseif ($Service -eq "mcp-reasoning-cost") {
    Write-Host "mcp-reasoning-cost doesn't require environment variables" -ForegroundColor Yellow
    Write-Host "Optional: LLM_INPUT_TOKEN_PRICE_PER_M, LLM_OUTPUT_TOKEN_PRICE_PER_M" -ForegroundColor Gray
    exit 0
}

# Update Cloud Run service
Write-Host ""
Write-Host "Updating Cloud Run service..." -ForegroundColor Cyan

$envVarsString = $envVars -join ","

$updateCmd = "gcloud run services update $Service " +
              "--region $Region " +
              "--set-env-vars $envVarsString " +
              "--project $ProjectId"

Invoke-Expression $updateCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Environment variables updated successfully" -ForegroundColor Green
    
    # Get service URL
    $serviceUrl = gcloud run services describe $Service --region $Region --format="value(status.url)" --project $ProjectId
    Write-Host ""
    Write-Host "Service URL: $serviceUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Test the service:" -ForegroundColor Yellow
    Write-Host "  Invoke-RestMethod -Uri `"$serviceUrl/health`"" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to update environment variables" -ForegroundColor Red
    exit 1
}

