# CortexMetaAgent MCP Servers

Model Control Protocol (MCP) servers for the CortexMetaAgent project, providing centralized monitoring, inventory tracking, and cost analysis capabilities.

## Overview

This repository contains MCP servers that integrate with CortexMetaAgent to provide:
- Agent inventory and metadata tracking
- Usage statistics and performance metrics
- Reasoning cost estimation and analysis

## MCP Servers

### 1. mcp-agent-inventory (Port 8001)
Agent metadata, usage tracking, and performance metrics server.

**Features:**
- Track agent metadata and configurations
- Monitor usage statistics and last run times
- Performance metrics collection

### 2. mcp-reasoning-cost (Port 8002)
Reasoning chain cost estimation server.

**Features:**
- Estimate reasoning costs based on chain-of-thought metrics
- Token usage analysis
- Cost optimization recommendations

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop (for containerized deployment)
- Google Cloud SDK (for Cloud Run deployment)

### Local Development

```powershell
# Install dependencies
cd mcp-servers
pip install -r requirements.txt

# Start servers individually
cd mcp-agent-inventory
python server.py

cd mcp-reasoning-cost
python server.py
```

### Docker Desktop Deployment

```powershell
# Deploy all services to Docker Desktop
cd mcp-servers
.\deploy-to-docker-desktop.ps1

# Build only (without starting)
.\deploy-to-docker-desktop.ps1 -BuildOnly

# Start only (without rebuilding)
.\deploy-to-docker-desktop.ps1 -StartOnly

# Stop all containers
.\deploy-to-docker-desktop.ps1 -Stop

# Remove all containers and images
.\deploy-to-docker-desktop.ps1 -Remove
```

**Prerequisites:**
- Docker Desktop for Windows must be installed and running
- Required environment variables (see Environment Variables section)

**Service URLs:**
- mcp-agent-inventory: http://localhost:8001
- mcp-reasoning-cost: http://localhost:8002

### Google Cloud Run Deployment

```powershell
# Deploy all services to Cloud Run
cd mcp-servers
.\deploy-to-cloud-run.ps1 -DeployAll

# Deploy specific service
.\deploy-to-cloud-run.ps1 -ServiceName "mcp-agent-inventory"
```

## Docker Compose

```powershell
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## Environment Variables

### mcp-agent-inventory

See `mcp-servers/mcp-agent-inventory/README.md` for required environment variables.

### mcp-reasoning-cost

See `mcp-servers/mcp-reasoning-cost/README.md` for required environment variables.

## Documentation

- [Docker Setup](mcp-servers/DOCKER.md) - Docker deployment guide
- [Cloud Run Deployment](mcp-servers/CLOUD_RUN.md) - Cloud Run deployment instructions
- [MCP Inspector Connection Guide](mcp-servers/MCP_INSPECTOR.md) - Connecting with MCP Inspector
- [MCP Server Details](../CortexMetaAgent/MCP_SERVERS.md) - Integration with CortexMetaAgent

## Architecture

```
mcp-servers/
├── mcp-agent-inventory/    # Agent inventory and metadata server
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
├── mcp-reasoning-cost/     # Reasoning cost estimation server
│   ├── server.py
│   ├── requirements.txt
│   └── README.md
├── docker-compose.yml       # Docker Compose configuration
├── deploy-to-docker-desktop.ps1
└── deploy-to-cloud-run.ps1
```

## Integration with CortexMetaAgent

These MCP servers are designed to work seamlessly with CortexMetaAgent:

1. **MetricsAgent** uses `mcp-agent-inventory` to track agent usage
2. **ReasoningCostAgent** uses `mcp-reasoning-cost` for cost analysis
3. **CortexMetaAgent** orchestrates both servers for comprehensive monitoring

See the main [CortexMetaAgent](https://github.com/nareshsaladi2024/CortexMetaAgent) repository for integration details.

## Development

### Adding a New MCP Server

1. Create a new directory under `mcp-servers/`
2. Implement the MCP server following the MCP SDK patterns
3. Add to `docker-compose.yml`
4. Update deployment scripts

### Testing

```powershell
# Test MCP Inspector connection
# See MCP_INSPECTOR.md for instructions

# Test individual server
curl http://localhost:8001/health
curl http://localhost:8002/health
```

## Repository

- **GitHub**: [CortexMetaAgent-MCPServers](https://github.com/nareshsaladi2024/CortexMetaAgent-MCPServers)
- **Main Project**: [CortexMetaAgent](https://github.com/nareshsaladi2024/CortexMetaAgent)
- **License**: MIT

## Contributing

This repository is part of the CortexMetaAgent project. See the main repository for contribution guidelines.
