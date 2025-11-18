# CortexEvalAI MCP Servers

This repository contains the Model Control Protocol (MCP) servers for the CortexEvalAI project.

## MCP Servers

### 1. mcp-tokenstats (Port 8000)
Token counting and cost calculation server using Google Gemini API.

### 2. mcp-agent-inventory (Port 8001)
Agent metadata, usage tracking, and performance metrics server.

### 3. mcp-reasoning-cost (Port 8002)
Reasoning chain cost estimation server.

## Quick Start

### Local Development

```powershell
# Start all servers with Docker Compose
cd mcp-servers
docker-compose up -d

# Or start individually
cd mcp-servers\mcp-tokenstats
.\run-server.ps1
```

### Deploy to Windows Docker Desktop

```powershell
# Deploy all services to Docker Desktop
cd mcp-servers
.\deploy-to-docker-desktop.ps1

.\deploy-to-docker-desktop.ps1 -BuildOnly

# Start only (without rebuilding)
.\deploy-to-docker-desktop.ps1 -StartOnly

# Deploy a specific service
.\deploy-to-docker-desktop.ps1 -Service mcp-tokenstats

# Stop all containers
.\deploy-to-docker-desktop.ps1 -Stop

# Remove all containers and images
.\deploy-to-docker-desktop.ps1 -Remove
```

**Prerequisites:**
- Docker Desktop for Windows must be installed and running
- Required environment variables (see Environment Variables section)

**Service URLs:**
- mcp-tokenstats: http://localhost:8000
- mcp-agent-inventory: http://localhost:8001
- mcp-reasoning-cost: http://localhost:8002

### Deploy to Google Cloud Run

```powershell
cd mcp-servers
.\deploy-to-cloud-run.ps1 -DeployAll
```

## Documentation

- [Docker Setup](mcp-servers/DOCKER.md)
- [Cloud Run Deployment](mcp-servers/CLOUD_RUN.md)
- [MCP Inspector Connection Guide](mcp-servers/MCP_INSPECTOR.md)
- [MCP Server Details](../../CortexEvalAI/MCP_SERVERS.md)

## Requirements

- Python 3.11+
- Docker (for containerized deployment)
- Google Cloud SDK (for Cloud Run deployment)

## Environment Variables

See individual server README files for required environment variables:
- `mcp-servers/mcp-tokenstats/README.md`
- `mcp-servers/mcp-agent-inventory/README.md`
- `mcp-servers/mcp-reasoning-cost/README.md`

