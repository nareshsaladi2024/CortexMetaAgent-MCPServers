# Building Separate MCP Server Docker Images

This guide explains how to build separate Docker images for MCP servers (separate from agents).

## MCP Server Images

The MCP servers are built as **separate Docker images** from the agents:

### 1. mcp-agent-inventory
- **Image**: `cortex-mcp-agent-inventory:latest`
- **Port**: 8001
- **Dockerfile**: `mcp-agent-inventory/Dockerfile`

### 2. mcp-reasoning-cost
- **Image**: `cortex-mcp-reasoning-cost:latest`
- **Port**: 8002
- **Dockerfile**: `mcp-reasoning-cost/Dockerfile`

## Building Individual MCP Server Images

### Build mcp-agent-inventory
```bash
cd C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers\mcp-agent-inventory
docker build -t cortex-mcp-agent-inventory:latest .
```

### Build mcp-reasoning-cost
```bash
cd C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers\mcp-reasoning-cost
docker build -t cortex-mcp-reasoning-cost:latest .
```

## Building All MCP Servers Together

```bash
cd C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers
docker-compose build
```

This will build both MCP server images:
- `cortex-mcp-agent-inventory:latest`
- `cortex-mcp-reasoning-cost:latest`

## Running MCP Servers

```bash
cd C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers
docker-compose up
```

Or run individually:
```bash
docker-compose up mcp-agent-inventory
docker-compose up mcp-reasoning-cost
```

## Image Separation

**Agents** are in a separate project:
- **Project**: `CortexMetaAgent`
- **Image**: `cortex-meta-agent:latest`
- **Location**: `C:\Capstone\CortexMetaAgent`

**MCP Servers** are in this project:
- **Project**: `CortexMetaAgent-MCPServers`
- **Images**: `cortex-mcp-agent-inventory:latest`, `cortex-mcp-reasoning-cost:latest`
- **Location**: `C:\Capstone\CortexMetaAgent-MCPServers\mcp-servers`

The agents and MCP servers are completely separate and can be built and run independently.

