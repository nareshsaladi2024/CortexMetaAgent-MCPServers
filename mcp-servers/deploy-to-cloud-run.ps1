# PowerShell script to deploy MCP servers to Google Cloud Run
# Requires: gcloud CLI, Docker, and appropriate permissions

param(
    [string]$ProjectId = "aiagent-capstoneproject",
    [string]$Region = "us-central1",
    [string]$ServiceAccount = "adk-agent-service@aiagent-capstoneproject.iam.gserviceaccount.com",
    [switch]$BuildOnly = $false,
    [switch]$DeployAll = $false
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deploy MCP Servers to Google Cloud Run" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if gcloud is installed
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: gcloud CLI is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Install from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "ERROR: Docker is not running or not accessible" -ForegroundColor Red
    exit 1
}

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Project: $ProjectId" -ForegroundColor White
Write-Host "  Region: $Region" -ForegroundColor White
Write-Host "  Service Account: $ServiceAccount" -ForegroundColor White
Write-Host ""

# Set the project
Write-Host "Setting GCP project..." -ForegroundColor Cyan
gcloud config set project $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to set project" -ForegroundColor Red
    exit 1
}

# Enable required APIs
Write-Host "Enabling required APIs..." -ForegroundColor Cyan
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
Write-Host ""

# Check permissions
Write-Host "Checking permissions..." -ForegroundColor Cyan
$currentAccount = gcloud config get-value account 2>&1
Write-Host "  Authenticated as: $currentAccount" -ForegroundColor Gray

# Check IAM permissions for Cloud Build
Write-Host "  Checking IAM permissions..." -ForegroundColor Gray
$hasCloudBuildPermission = $false

try {
    $iamPolicy = gcloud projects get-iam-policy $ProjectId --flatten="bindings[].members" --format="value(bindings.role)" --filter="bindings.members:user:$currentAccount" 2>&1 | Out-String
    
    if ($LASTEXITCODE -eq 0 -and $iamPolicy) {
        if ($iamPolicy -match "cloudbuild\.builds\.(editor|builder|admin)" -or 
            $iamPolicy -match "roles/owner" -or 
            $iamPolicy -match "roles/editor") {
            $hasCloudBuildPermission = $true
        }
    }
} catch {
    # If we can't check IAM policy, we'll warn but continue
    Write-Host "  Could not verify IAM permissions (this is OK if you're not a project owner)" -ForegroundColor Yellow
}

if (-not $hasCloudBuildPermission) {
    Write-Host ""
    Write-Host "WARNING: Your account may not have permission to submit Cloud Build jobs" -ForegroundColor Yellow
    Write-Host "  The build may fail with PERMISSION_DENIED error." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Required IAM roles:" -ForegroundColor Cyan
    Write-Host "  - roles/cloudbuild.builds.editor (or roles/cloudbuild.builds.builder)" -ForegroundColor Gray
    Write-Host "  - roles/storage.admin (for Cloud Build storage)" -ForegroundColor Gray
    Write-Host "  - roles/run.admin (for Cloud Run deployment)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To grant permissions, ask a project owner to run:" -ForegroundColor Yellow
    Write-Host "  gcloud projects add-iam-policy-binding $ProjectId `" -ForegroundColor Gray
    Write-Host "    --member=`"user:$currentAccount`" `" -ForegroundColor Gray
    Write-Host "    --role=`"roles/cloudbuild.builds.editor`"" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  gcloud projects add-iam-policy-binding $ProjectId `" -ForegroundColor Gray
    Write-Host "    --member=`"user:$currentAccount`" `" -ForegroundColor Gray
    Write-Host "    --role=`"roles/storage.admin`"" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  gcloud projects add-iam-policy-binding $ProjectId `" -ForegroundColor Gray
    Write-Host "    --member=`"user:$currentAccount`" `" -ForegroundColor Gray
    Write-Host "    --role=`"roles/run.admin`"" -ForegroundColor Gray
    Write-Host ""
    $response = Read-Host "Continue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }
} else {
    Write-Host "  Cloud Build permissions OK" -ForegroundColor Green
}
Write-Host ""

# Define services
$services = @(
    @{
        Name = "mcp-tokenstats"
        Directory = "mcp-tokenstats"
        Image = "gcr.io/$ProjectId/mcp-tokenstats:latest"
        ServiceName = "mcp-tokenstats"
        EnvVars = @("GOOGLE_API_KEY")
    },
    @{
        Name = "mcp-agent-inventory"
        Directory = "mcp-agent-inventory"
        Image = "gcr.io/$ProjectId/mcp-agent-inventory:latest"
        ServiceName = "mcp-agent-inventory"
        EnvVars = @("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_NUMBER", "GCP_LOCATION")
        ServiceAccount = $ServiceAccount
    },
    @{
        Name = "mcp-reasoning-cost"
        Directory = "mcp-reasoning-cost"
        Image = "gcr.io/$ProjectId/mcp-reasoning-cost:latest"
        ServiceName = "mcp-reasoning-cost"
        EnvVars = @()
    }
)

# Function to build and deploy a service
function Deploy-Service {
    param(
        [hashtable]$Service,
        [string]$ProjectId,
        [string]$Region
    )
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Deploying $($Service.Name)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $serviceDir = Join-Path $PSScriptRoot $Service.Directory
    
    if (-not (Test-Path $serviceDir)) {
        Write-Host "ERROR: Service directory not found: $serviceDir" -ForegroundColor Red
        return $false
    }
    
    Push-Location $serviceDir
    
    try {
        # Build the container image
        Write-Host "Building container image..." -ForegroundColor Cyan
        Write-Host "  Image: $($Service.Image)" -ForegroundColor Gray
        
        gcloud builds submit --tag $($Service.Image) --project $ProjectId
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Build failed for $($Service.Name)" -ForegroundColor Red
            return $false
        }
        
        Write-Host "[OK] Image built successfully" -ForegroundColor Green
        
        if ($BuildOnly) {
            Write-Host "Build-only mode: Skipping deployment" -ForegroundColor Yellow
            return $true
        }
        
        # Prepare environment variables
        $envVars = @()
        foreach ($envVar in $Service.EnvVars) {
            $value = [Environment]::GetEnvironmentVariable($envVar, "Process")
            if ($value) {
                $envVars += "--set-env-vars=$envVar=$value"
            } else {
                Write-Host "WARNING: Environment variable $envVar is not set" -ForegroundColor Yellow
            }
        }
        
        # Deploy to Cloud Run
        Write-Host "Deploying to Cloud Run..." -ForegroundColor Cyan
        
        $deployCmd = "gcloud run deploy $($Service.ServiceName) " +
                     "--image $($Service.Image) " +
                     "--platform managed " +
                     "--region $Region " +
                     "--allow-unauthenticated " +
                     "--project $ProjectId"
        
        if ($Service.ServiceAccount) {
            $deployCmd += " --service-account $($Service.ServiceAccount)"
        }
        
        if ($envVars.Count -gt 0) {
            $deployCmd += " " + ($envVars -join " ")
        }
        
        Invoke-Expression $deployCmd
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] $($Service.Name) deployed successfully" -ForegroundColor Green
            
            # Get the service URL
            $serviceUrl = gcloud run services describe $($Service.ServiceName) --region $Region --format="value(status.url)" --project $ProjectId
            Write-Host "  Service URL: $serviceUrl" -ForegroundColor Cyan
            return $true
        } else {
            Write-Host "ERROR: Deployment failed for $($Service.Name)" -ForegroundColor Red
            return $false
        }
    } finally {
        Pop-Location
    }
}

# Deploy services
$results = @()

if ($DeployAll) {
    foreach ($service in $services) {
        $success = Deploy-Service -Service $service -ProjectId $ProjectId -Region $Region
        $results += @{
            Name = $service.Name
            Success = $success
        }
    }
} else {
    Write-Host "Select service to deploy:" -ForegroundColor Yellow
    Write-Host "  1. mcp-tokenstats" -ForegroundColor White
    Write-Host "  2. mcp-agent-inventory" -ForegroundColor White
    Write-Host "  3. mcp-reasoning-cost" -ForegroundColor White
    Write-Host "  4. All services" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "Enter choice (1-4)"
    
    switch ($choice) {
        "1" { $selectedServices = @($services[0]) }
        "2" { $selectedServices = @($services[1]) }
        "3" { $selectedServices = @($services[2]) }
        "4" { $selectedServices = $services }
        default {
            Write-Host "Invalid choice" -ForegroundColor Red
            exit 1
        }
    }
    
    foreach ($service in $selectedServices) {
        $success = Deploy-Service -Service $service -ProjectId $ProjectId -Region $Region
        $results += @{
            Name = $service.Name
            Success = $success
        }
    }
}

# Print summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($result in $results) {
    if ($result.Success) {
        Write-Host "[OK] $($result.Name)" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] $($result.Name)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "To view deployed services:" -ForegroundColor Cyan
Write-Host "  gcloud run services list --region $Region --project $ProjectId" -ForegroundColor White
Write-Host ""

