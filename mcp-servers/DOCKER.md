# Docker Setup for MCP Servers

This directory contains Docker configurations for all three MCP servers:
- **mcp-tokenstats** (Port 8000) - Token counting and cost calculation
- **mcp-agent-inventory** (Port 8001) - Agent metadata and usage tracking
- **mcp-reasoning-cost** (Port 8002) - Reasoning chain cost estimation

## Quick Start

### Prerequisites
- Docker Desktop for Windows installed and running
- Docker Compose installed (included with Docker Desktop)
- Environment variables configured (see below)

### Deploy to Windows Docker Desktop (Recommended)

Use the automated deployment script:

```powershell
cd mcp-servers
.\deploy-to-docker-desktop.ps1
```

This script will:
- Check if Docker is running
- Verify environment variables
- Build all Docker images
- Start all containers
- Display service URLs and status

**Options:**
- `-BuildOnly`: Only build images without starting containers
- `-StartOnly`: Only start containers without rebuilding
- `-Service <name>`: Deploy only a specific service
- `-Stop`: Stop all running containers
- `-Remove`: Stop and remove all containers and images

### Start All Servers (Manual)

Alternatively, you can use docker-compose directly:

```bash
cd mcp-servers
docker-compose up -d
```

### Stop All Servers

```bash
docker-compose down
```

### View Logs

```bash
# All servers
docker-compose logs -f

# Specific server
docker-compose logs -f mcp-tokenstats
docker-compose logs -f mcp-agent-inventory
docker-compose logs -f mcp-reasoning-cost
```

## Environment Variables

### Method 1: Using Helper Script (Recommended)

Use the helper script to create a `.env` file:

```powershell
cd mcp-servers
.\set-docker-env-vars.ps1 -UseEnvFile -GoogleApiKey "your-api-key"
```

This will create a `.env` file that docker-compose will automatically load.

### Method 2: Manual .env File

Create a `.env` file in the `mcp-servers` directory:

```bash
# Required for mcp-tokenstats
GOOGLE_API_KEY=your-gemini-api-key

# Required for mcp-agent-inventory
GOOGLE_CLOUD_PROJECT=your-project-id
GCP_PROJECT_NUMBER=your-project-number
GOOGLE_CLOUD_LOCATION=us-central1

# Optional pricing overrides for mcp-reasoning-cost
LLM_INPUT_TOKEN_PRICE_PER_M=1.25
LLM_OUTPUT_TOKEN_PRICE_PER_M=10.00
```

### Method 3: PowerShell Environment Variables

Set environment variables in your PowerShell session:

```powershell
$env:GOOGLE_API_KEY = "your-gemini-api-key"
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
$env:GCP_PROJECT_NUMBER = "your-project-number"
$env:GOOGLE_CLOUD_LOCATION = "us-central1"
```

**Note:** PowerShell environment variables are session-specific. Use `.env` file for persistence.

### View Current Environment Variables

```powershell
.\set-docker-env-vars.ps1 -ShowCurrent
```

## Individual Server Builds

### Build Individual Images

```bash
# Build mcp-tokenstats
cd mcp-tokenstats
docker build -t mcp-tokenstats:latest .

# Build mcp-agent-inventory
cd ../mcp-agent-inventory
docker build -t mcp-agent-inventory:latest .

# Build mcp-reasoning-cost
cd ../mcp-reasoning-cost
docker build -t mcp-reasoning-cost:latest .
```

### Run Individual Containers

```bash
# mcp-tokenstats
docker run -d \
  --name mcp-tokenstats \
  -p 8000:8000 \
  -e GOOGLE_API_KEY=your-api-key \
  mcp-tokenstats:latest

# mcp-agent-inventory
docker run -d \
  --name mcp-agent-inventory \
  -p 8001:8001 \
  -e GOOGLE_CLOUD_PROJECT=your-project-id \
  -e GCP_PROJECT_NUMBER=your-project-number \
  -v $(pwd)/mcp-agent-inventory/aiagent-capstoneproject-10beb4eeaf31.json:/app/credentials.json:ro \
  mcp-agent-inventory:latest

# mcp-reasoning-cost
docker run -d \
  --name mcp-reasoning-cost \
  -p 8002:8002 \
  mcp-reasoning-cost:latest
```

## Health Checks

All services include health checks. Check status:

```bash
docker-compose ps
```

Or test endpoints directly:

```bash
# mcp-tokenstats
curl http://localhost:8000/health

# mcp-agent-inventory
curl http://localhost:8001/health

# mcp-reasoning-cost
curl http://localhost:8002/health
```

## Development Mode

For development with live code reloading, use volume mounts:

1. Copy `docker-compose.override.yml.example` to `docker-compose.override.yml`
2. Customize environment variables
3. Run `docker-compose up`

The override file mounts local directories for live code changes.

## Troubleshooting

### Check Container Logs

```bash
docker-compose logs mcp-tokenstats
docker-compose logs mcp-agent-inventory
docker-compose logs mcp-reasoning-cost
```

### Restart a Specific Service

```bash
docker-compose restart mcp-tokenstats
```

### Rebuild After Code Changes

```bash
docker-compose build mcp-tokenstats
docker-compose up -d mcp-tokenstats
```

### Remove All Containers and Volumes

```bash
docker-compose down -v
```

## Service Account Credentials

The `mcp-agent-inventory` service requires Google Cloud credentials. The service account JSON file is mounted as a read-only volume:

```yaml
volumes:
  - ./mcp-agent-inventory/aiagent-capstoneproject-10beb4eeaf31.json:/app/credentials.json:ro
```

Ensure the file exists before starting the container.

## Network

All services are on the same Docker network (`mcp-servers-network`) and can communicate with each other using service names:

- `http://mcp-tokenstats:8000`
- `http://mcp-agent-inventory:8001`
- `http://mcp-reasoning-cost:8002`

## Ports

- **8000**: mcp-tokenstats
- **8001**: mcp-agent-inventory
- **8002**: mcp-reasoning-cost

Make sure these ports are not in use by other services.

