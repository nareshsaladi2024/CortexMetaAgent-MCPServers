# Connecting MCP Inspector to MCP Servers

This guide explains how to connect MCP Inspector to your MCP servers running on Docker Desktop or Cloud Run.

## Understanding MCP Transport Methods

MCP servers can be accessed via different transport methods:
- **HTTP POST** - Standard REST API (already implemented)
- **SSE (Server-Sent Events)** - For real-time streaming (recommended for MCP Inspector)
- **stdio** - For local process communication

## Current Server Endpoints

All servers expose the MCP protocol at:
- **POST /** - MCP JSON-RPC 2.0 endpoint (standard HTTP)
- **GET /sse** or **POST /sse** - MCP protocol via Server-Sent Events (SSE) for streamable HTTP
- **GET /health** - Health check endpoint

### SSE Endpoints (Recommended for MCP Inspector)

The SSE endpoints support:
- `initialize` - Initialize MCP connection
- `tools/list` - List available tools ✅
- `tools/call` - Call tools (fully implemented for mcp-tokenstats, partial for others)

### Service URLs

**Local Docker Desktop:**
- mcp-tokenstats: `http://localhost:8000`
- mcp-agent-inventory: `http://localhost:8001`
- mcp-reasoning-cost: `http://localhost:8002`

**Cloud Run (after deployment):**
- Get URLs with: `gcloud run services list --region us-central1`

## Connecting with MCP Inspector

### Method 1: Using SSE Endpoint (Recommended for Streamable HTTP)

MCP Inspector with streamable HTTP should use the SSE endpoint. Configure it as follows:

#### For Local Docker Desktop:

1. **Start your servers:**
   ```powershell
   cd mcp-servers
   .\deploy-to-docker-desktop.ps1
   ```

2. **In MCP Inspector, configure the server:**
   - **Transport**: SSE (Server-Sent Events) or Streamable HTTP
   - **URL**: `http://localhost:8000/sse` (for mcp-tokenstats)
   - **Method**: POST or GET
   - The SSE endpoint will stream responses in `text/event-stream` format

3. **Test the SSE endpoint:**
   ```powershell
   $body = @{
       jsonrpc = "2.0"
       id = 1
       method = "tools/list"
       params = @{}
   } | ConvertTo-Json
   
   Invoke-RestMethod -Uri "http://localhost:8000/sse" -Method POST -Body $body -ContentType "application/json"
   ```

### Method 2: Using HTTP POST Endpoint (Standard)

MCP Inspector can also connect directly to the HTTP POST endpoint. Configure it as follows:

#### For Local Docker Desktop:

1. **Start your servers:**
   ```powershell
   cd mcp-servers
   .\deploy-to-docker-desktop.ps1
   ```

2. **In MCP Inspector, configure the server:**
   - **Transport**: HTTP
   - **URL**: `http://localhost:8000` (for mcp-tokenstats)
   - **Method**: POST
   - **Endpoint**: `/`

3. **Test the connection:**
   ```powershell
   # Test initialize
   $body = @{
       jsonrpc = "2.0"
       id = 1
       method = "initialize"
       params = @{
           protocolVersion = "2024-11-05"
           capabilities = @{}
           clientInfo = @{
               name = "mcp-inspector"
               version = "1.0.0"
           }
       }
   } | ConvertTo-Json -Depth 10
   
   Invoke-RestMethod -Uri "http://localhost:8000/" -Method POST -Body $body -ContentType "application/json"
   ```

#### For Cloud Run:

1. **Get your service URL:**
   ```powershell
   $url = gcloud run services describe mcp-tokenstats --region us-central1 --format="value(status.url)"
   Write-Host "Service URL: $url"
   ```

2. **In MCP Inspector (SSE - Recommended):**
   - **Transport**: SSE or Streamable HTTP
   - **URL**: `$url/sse` (append /sse to the service URL)
   - **Method**: POST or GET

3. **In MCP Inspector (Standard HTTP):**
   - **Transport**: HTTP
   - **URL**: `$url` (from above)
   - **Method**: POST
   - **Endpoint**: `/`

### Method 2: Using MCP Inspector Proxy (Recommended)

MCP Inspector includes a proxy server that can bridge connections:

1. **Start MCP Inspector proxy:**
   ```bash
   npx @modelcontextprotocol/inspector
   ```

2. **Configure the proxy to connect to your server:**
   - The proxy will provide a local URL (typically `http://localhost:5173`)
   - Configure it to forward to your MCP server URL

3. **Access MCP Inspector UI:**
   - Open the URL provided by the proxy
   - Configure the server connection in the UI

### Method 3: Direct stdio (For Local Development)

For local development without Docker, you can run servers directly:

```powershell
# In one terminal
cd mcp-servers\mcp-tokenstats
python server.py

# In MCP Inspector, configure:
# Transport: stdio
# Command: python
# Args: server.py
# Working Directory: C:\AI Agents\CortexEvalAI-MCPServers\mcp-servers\mcp-tokenstats
```

## Troubleshooting

### Issue: "Cannot connect to server"

**Solutions:**
1. **Verify server is running:**
   ```powershell
   # For Docker Desktop
   docker ps
   
   # Test health endpoint
   Invoke-RestMethod -Uri "http://localhost:8000/health"
   ```

2. **Check firewall/network:**
   - Ensure ports 8000, 8001, 8002 are not blocked
   - For Cloud Run, verify the service is publicly accessible

3. **Check CORS:**
   - Servers have CORS enabled with `allow_origins=["*"]`
   - If issues persist, check browser console for CORS errors

### Issue: "Tools not listed"

**Solutions:**
1. **Test tools/list endpoint:**
   ```powershell
   $body = @{
       jsonrpc = "2.0"
       id = 2
       method = "tools/list"
       params = @{}
   } | ConvertTo-Json
   
   Invoke-RestMethod -Uri "http://localhost:8000/" -Method POST -Body $body -ContentType "application/json"
   ```

2. **Verify initialize was called first:**
   - MCP protocol requires `initialize` before `tools/list`
   - Ensure MCP Inspector calls initialize first

### Issue: "Method not found" errors

**Solutions:**
1. **Check method names:**
   - mcp-tokenstats: `tokenize`
   - mcp-agent-inventory: `register_agent`, `record_execution`, `get_agent_metrics`, etc.
   - mcp-reasoning-cost: `estimate_reasoning_cost`

2. **Verify JSON-RPC format:**
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "tools/list",
     "params": {}
   }
   ```

### Issue: Cloud Run connection fails

**Solutions:**
1. **Verify service is deployed:**
   ```powershell
   gcloud run services list --region us-central1
   ```

2. **Check authentication:**
   - Cloud Run services are deployed with `--allow-unauthenticated`
   - If authentication is required, add IAM policy binding

3. **Test from command line:**
   ```powershell
   $url = gcloud run services describe mcp-tokenstats --region us-central1 --format="value(status.url)"
   Invoke-RestMethod -Uri "$url/health"
   ```

## Testing MCP Protocol Endpoints

### Test Initialize

```powershell
$initBody = @{
    jsonrpc = "2.0"
    id = 1
    method = "initialize"
    params = @{
        protocolVersion = "2024-11-05"
        capabilities = @{}
        clientInfo = @{
            name = "test-client"
            version = "1.0.0"
        }
    }
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method POST -Body $initBody -ContentType "application/json"
$response | ConvertTo-Json
```

### Test Tools List

```powershell
$toolsBody = @{
    jsonrpc = "2.0"
    id = 2
    method = "tools/list"
    params = @{}
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method POST -Body $toolsBody -ContentType "application/json"
$response | ConvertTo-Json
```

### Test Tool Call

```powershell
$callBody = @{
    jsonrpc = "2.0"
    id = 3
    method = "tools/call"
    params = @{
        name = "tokenize"
        arguments = @{
            model = "gemini-2.5-flash"
            prompt = "Hello, world!"
            generate = $false
        }
    }
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod -Uri "http://localhost:8000/" -Method POST -Body $callBody -ContentType "application/json"
$response | ConvertTo-Json
```

## MCP Inspector Configuration Examples

### Configuration for mcp-tokenstats (Local)

```json
{
  "mcpServers": {
    "tokenstats": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", "@-",
        "http://localhost:8000/"
      ],
      "transport": "stdio"
    }
  }
}
```

### Configuration for mcp-tokenstats (Cloud Run)

```json
{
  "mcpServers": {
    "tokenstats": {
      "url": "https://mcp-tokenstats-xxxxx-uc.a.run.app",
      "transport": "http",
      "method": "POST",
      "endpoint": "/"
    }
  }
}
```

## Next Steps

1. **Verify server health:**
   ```powershell
   # Local
   Invoke-RestMethod -Uri "http://localhost:8000/health"
   
   # Cloud Run
   Invoke-RestMethod -Uri "$cloudRunUrl/health"
   ```

2. **Test MCP protocol:**
   - Use the test scripts above to verify endpoints work

3. **Configure MCP Inspector:**
   - Use the configuration examples above
   - Start with local Docker Desktop, then test Cloud Run

4. **Check server logs:**
   ```powershell
   # Docker Desktop
   docker logs mcp-tokenstats
   
   # Cloud Run
   gcloud run services logs read mcp-tokenstats --region us-central1
   ```

## Additional Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [MCP Inspector GitHub](https://github.com/modelcontextprotocol/inspector)
- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)

