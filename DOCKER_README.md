# Docker Deployment Guide for CortexMetaAgent MCP Servers

This guide explains how to build and run the MCP servers using Docker.

## Overview

CortexMetaAgent-MCPServers consists of 2 MCP servers:
- **mcp-agent-inventory**: Agent inventory management server (port 8001)
- **mcp-reasoning-cost**: Reasoning cost analysis server (port 8002)

## Prerequisites

1. **Docker Desktop** installed and running
2. **.env file** configured in `mcp-servers/` directory (copied from Day1a)
3. **Service account JSON** file (if using Vertex AI)

## Quick Start

### Build and Start All MCP Servers

```bash
cd C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers
docker-compose up --build
```

### Run in Detached Mode

```bash
docker-compose up -d --build
```

## Services

### mcp-agent-inventory
- **Container**: `mcp-agent-inventory`
- **Image**: `cortex-mcp-agent-inventory:latest`
- **Port**: 8001
- **Health Check**: http://localhost:8001/health

### mcp-reasoning-cost
- **Container**: `mcp-reasoning-cost`
- **Image**: `cortex-mcp-reasoning-cost:latest`
- **Port**: 8002
- **Health Check**: http://localhost:8002/health

## Environment Variables

### mcp-agent-inventory
- `PORT`: Server port (default: 8001)
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GCP_PROJECT_ID`: GCP project ID
- `GCP_PROJECT_NUMBER`: GCP project number
- `GCP_LOCATION`: GCP location (default: us-central1)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account JSON

### mcp-reasoning-cost
- `PORT`: Server port (default: 8002)
- `LLM_INPUT_TOKEN_PRICE_PER_M`: Input token price (default: 1.25)
- `LLM_OUTPUT_TOKEN_PRICE_PER_M`: Output token price (default: 10.00)
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `GOOGLE_CLOUD_LOCATION`: GCP location

## Docker Commands

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f mcp-agent-inventory
docker-compose logs -f mcp-reasoning-cost
```

### Stop Services
```bash
docker-compose down
```

### Rebuild After Code Changes
```bash
docker-compose up --build
```

### Run Specific Server
```bash
docker-compose up mcp-agent-inventory
```

### Access Container Shell
```bash
docker exec -it mcp-agent-inventory /bin/bash
docker exec -it mcp-reasoning-cost /bin/bash
```

## Building Individual Images

```bash
# Build agent-inventory image
docker build -t cortex-mcp-agent-inventory:latest -f mcp-agent-inventory/Dockerfile mcp-agent-inventory/

# Build reasoning-cost image
docker build -t cortex-mcp-reasoning-cost:latest -f mcp-reasoning-cost/Dockerfile mcp-reasoning-cost/
```

## Testing

### Test Health Endpoints
```bash
# Agent Inventory
curl http://localhost:8001/health

# Reasoning Cost
curl http://localhost:8002/health
```

## Troubleshooting

### Port Already in Use
Edit `docker-compose.yml` and change the port mapping:
```yaml
ports:
  - "8003:8001"  # Use 8003 instead of 8001
```

### Environment Variables Not Loading
1. Check that `.env` file exists in `mcp-servers/` directory
2. Verify `env_file` configuration in `docker-compose.yml`
3. Check container logs: `docker-compose logs`

### Service Account Authentication
1. Ensure service account JSON exists
2. Verify volume mount path in `docker-compose.yml`
3. Check `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Server Not Starting
1. Check logs: `docker-compose logs mcp-agent-inventory`
2. Verify Python dependencies are installed
3. Check for import errors in logs

## Notes

- Both servers use FastAPI with uvicorn
- Health checks are configured for both servers
- `.env` file is loaded from `mcp-servers/` directory
- Service account JSON is mounted from kaggle-5-day-agents directory
- Servers run on ports 8001 and 8002 to avoid conflicts

