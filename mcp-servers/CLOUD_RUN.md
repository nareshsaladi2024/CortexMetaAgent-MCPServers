# Deploying MCP Servers to Google Cloud Run

This guide explains how to deploy the MCP servers to Google Cloud Run for production use.

## Prerequisites

1. **Google Cloud SDK (gcloud CLI)** installed and configured
2. **Docker** installed and running
3. **Google Cloud Project** with billing enabled
4. **Required APIs enabled**:
   - Cloud Run API
   - Cloud Build API
   - Artifact Registry API

## Quick Start

### 1. Set Environment Variables

```powershell
# Required for mcp-tokenstats
$env:GOOGLE_API_KEY = "your-gemini-api-key"

# Required for mcp-agent-inventory
$env:GOOGLE_CLOUD_PROJECT = "aiagent-capstoneproject"
$env:GCP_PROJECT_NUMBER = "1276251306"
$env:GCP_LOCATION = "us-central1"
```

### 2. Deploy All Services

```powershell
cd mcp-servers
.\deploy-to-cloud-run.ps1 -DeployAll
```

### 3. Deploy Individual Service

```powershell
.\deploy-to-cloud-run.ps1
# Then select the service number (1-4)
```

## Manual Deployment Steps

### Build and Deploy mcp-tokenstats

```powershell
cd mcp-tokenstats

# Build the image
gcloud builds submit --tag gcr.io/aiagent-capstoneproject/mcp-tokenstats:latest

# Deploy to Cloud Run
gcloud run deploy mcp-tokenstats `
  --image gcr.io/aiagent-capstoneproject/mcp-tokenstats:latest `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --set-env-vars GOOGLE_API_KEY=your-api-key `
  --project aiagent-capstoneproject
```

### Build and Deploy mcp-agent-inventory

```powershell
cd mcp-agent-inventory

# Build the image
gcloud builds submit --tag gcr.io/aiagent-capstoneproject/mcp-agent-inventory:latest

# Deploy to Cloud Run
gcloud run deploy mcp-agent-inventory `
  --image gcr.io/aiagent-capstoneproject/mcp-agent-inventory:latest `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --service-account adk-agent-service@aiagent-capstoneproject.iam.gserviceaccount.com `
  --set-env-vars GOOGLE_CLOUD_PROJECT=aiagent-capstoneproject,GCP_PROJECT_NUMBER=1276251306,GCP_LOCATION=us-central1 `
  --project aiagent-capstoneproject
```

### Build and Deploy mcp-reasoning-cost

```powershell
cd mcp-reasoning-cost

# Build the image
gcloud builds submit --tag gcr.io/aiagent-capstoneproject/mcp-reasoning-cost:latest

# Deploy to Cloud Run
gcloud run deploy mcp-reasoning-cost `
  --image gcr.io/aiagent-capstoneproject/mcp-reasoning-cost:latest `
  --platform managed `
  --region us-central1 `
  --allow-unauthenticated `
  --project aiagent-capstoneproject
```

## Using Cloud Build

Build all images at once using Cloud Build:

```powershell
cd mcp-servers
gcloud builds submit --config=cloudbuild.yaml
```

This will build and push all three images to Google Container Registry.

## Environment Variables

### mcp-tokenstats
- `GOOGLE_API_KEY` (required) - Gemini API key for token counting

### mcp-agent-inventory
- `GOOGLE_CLOUD_PROJECT` (required) - GCP project ID
- `GCP_PROJECT_NUMBER` (required) - GCP project number
- `GCP_LOCATION` (optional) - Default: us-central1
- Service account credentials (via service account binding)

### mcp-reasoning-cost
- `LLM_INPUT_TOKEN_PRICE_PER_M` (optional) - Default: 1.25
- `LLM_OUTPUT_TOKEN_PRICE_PER_M` (optional) - Default: 10.00

## Service URLs

After deployment, get service URLs:

```powershell
# Get all service URLs
gcloud run services list --region us-central1 --project aiagent-capstoneproject

# Get specific service URL
gcloud run services describe mcp-tokenstats --region us-central1 --format="value(status.url)"
```

## Update Configuration

After deployment, update `config.py` in the main project:

```python
MCP_TOKENSTATS_URL = "https://mcp-tokenstats-xxxxx.run.app"
MCP_AGENT_INVENTORY_URL = "https://mcp-agent-inventory-xxxxx.run.app"
MCP_REASONING_COST_URL = "https://mcp-reasoning-cost-xxxxx.run.app"
```

## Updating Services

To update a service after code changes:

```powershell
# Rebuild and redeploy
cd mcp-servers
.\deploy-to-cloud-run.ps1
# Select the service to update
```

Or manually:

```powershell
cd mcp-tokenstats
gcloud builds submit --tag gcr.io/aiagent-capstoneproject/mcp-tokenstats:latest
gcloud run deploy mcp-tokenstats --image gcr.io/aiagent-capstoneproject/mcp-tokenstats:latest --region us-central1
```

## Monitoring

View logs:

```powershell
# All services
gcloud logging read "resource.type=cloud_run_revision" --limit 50

# Specific service
gcloud run services logs read mcp-tokenstats --region us-central1
```

## Cost Optimization

Cloud Run charges based on:
- **CPU and memory** allocated
- **Request count**
- **Request duration**

Default settings:
- CPU: 1 vCPU
- Memory: 512 MiB
- Min instances: 0 (scales to zero)
- Max instances: 10

To adjust:

```powershell
gcloud run services update mcp-tokenstats `
  --cpu 2 `
  --memory 1Gi `
  --min-instances 1 `
  --max-instances 5 `
  --region us-central1
```

## Security

### Service Account

The `mcp-agent-inventory` service uses a service account for GCP API access. Ensure the service account has:
- `roles/aiplatform.user` - For Reasoning Engine API
- `roles/monitoring.viewer` - For Cloud Monitoring API

### Authentication

By default, services are deployed with `--allow-unauthenticated`. To require authentication:

```powershell
gcloud run services update mcp-tokenstats `
  --no-allow-unauthenticated `
  --region us-central1
```

Then grant access:

```powershell
gcloud run services add-iam-policy-binding mcp-tokenstats `
  --member="user:your-email@example.com" `
  --role="roles/run.invoker" `
  --region us-central1
```

## Troubleshooting

### Check Service Status

```powershell
gcloud run services describe mcp-tokenstats --region us-central1
```

### View Recent Logs

```powershell
gcloud run services logs read mcp-tokenstats --region us-central1 --limit 50
```

### Test Health Endpoints

```powershell
# Get service URL
$url = gcloud run services describe mcp-tokenstats --region us-central1 --format="value(status.url)"

# Test health
curl "$url/health"
```

### Common Issues

1. **Build fails**: Check Dockerfile syntax and dependencies
2. **Deployment fails**: Verify environment variables are set
3. **Service not accessible**: Check IAM permissions and authentication settings
4. **High latency**: Consider increasing CPU/memory or setting min-instances > 0

