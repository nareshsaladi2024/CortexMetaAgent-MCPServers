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

### Deploy to Google Cloud Run

```powershell
cd mcp-servers
.\deploy-to-cloud-run.ps1 -DeployAll
```

## Documentation

- [Docker Setup](mcp-servers/DOCKER.md)
- [Cloud Run Deployment](mcp-servers/CLOUD_RUN.md)
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

