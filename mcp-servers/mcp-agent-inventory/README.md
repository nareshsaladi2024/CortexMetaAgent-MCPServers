# AgentInventory MCP Server

Remote MCP (Model Control Protocol) server for tracking agent usage, executions, and performance metrics.

## Features

- **Agent Tracking**: Track multiple agents and their execution history
- **Usage Statistics**: Get detailed usage statistics including:
  - Count of executions
  - Token usage per execution
  - Last run time
  - Failure rate
  - Average runtime
  - Success/failure counts
- **Execution Recording**: Record agent executions with detailed metrics
- **Performance Monitoring**: Monitor agent performance over time

## Setup

### 1. Install Dependencies

```powershell
cd "C:\AI Agents\CortexEvalAI\mcp-servers\mcp-agent-inventory"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

Create a `.env` file:

```env
PORT=8001
GCP_PROJECT_ID=your-gcp-project
GCP_PROJECT_NUMBER=1276251306
GCP_LOCATION=us-central1
GCP_API_KEY=AIzaSyCI-zsRP85UVOi0DjtiCwWBwQ1djDy741g
```

Or set it in PowerShell:

```powershell
$env:PORT = 8001
$env:GCP_PROJECT_ID = "your-gcp-project"
$env:GCP_PROJECT_NUMBER = "1276251306"
$env:GCP_LOCATION = "us-central1"
$env:GCP_API_KEY = "AIzaSyCI-zsRP85UVOi0DjtiCwWBwQ1djDy741g"
```

**Note:** 
- The `GCP_PROJECT_ID` variable is required for the MCP Reasoning Engine endpoints (`/mcp-reas-engine/*`). 
- `GCP_PROJECT_NUMBER` is recommended (the numeric project ID, e.g., `1276251306`). If not set, the server will try to fetch it automatically from the project ID, but setting it directly is faster and more reliable.
- `GCP_LOCATION` is the region where your agents are deployed (defaults to `us-central1`). The server will check this region first, then fall back to `global` if needed.
- **Authentication**: The Reasoning Engine API requires OAuth2 authentication (not API keys). You must configure one of:
  - `GOOGLE_APPLICATION_CREDENTIALS`: Path to your GCP service account JSON key file (recommended)
  - Or run `gcloud auth application-default login` to use your user account
- `GCP_API_KEY` is optional and only used for fetching project number from Resource Manager API (if `GCP_PROJECT_NUMBER` is not set). The Reasoning Engine API does NOT support API keys and will always use OAuth2.
- If GCP variables are not set, those endpoints will return errors. The server will still work for local agent inventory tracking without GCP configuration.

**Finding Your Project Number:**
- Go to: https://console.cloud.google.com/iam-admin/settings?project=your-project-id
- Or run: `gcloud projects describe your-project-id --format="value(projectNumber)"`

**Setting Up Authentication:**
- **Service Account (Recommended)**: Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of your service account JSON file
- **User Account**: Run `gcloud auth application-default login` to authenticate with your user account

### 3. Run the Server

**Recommended: Use the run script:**

```powershell
.\run-server.ps1
```

**Alternative: Direct Python execution:**

```powershell
python server.py
```

Or using uvicorn directly:

```powershell
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

The server will start on `http://localhost:8001`

## API Endpoints

### GET /list_agents

List all agents in the inventory.

**Response:**
```json
{
  "agents": [
    {
      "id": "retriever",
      "description": "Document retrieval via vector search",
      "avg_cost": 0.0008,
      "avg_latency": 420.0
    },
    {
      "id": "summarizer",
      "description": "Long document compressor",
      "avg_cost": 0.003,
      "avg_latency": 760.0
    }
  ]
}
```

### GET /usage?agent={agent_id}

Get detailed usage statistics for a specific agent.

**Parameters:**
- `agent`: The ID of the agent (query parameter)

**Response:**
```json
{
  "total_runs": 488,
  "failures": 15,
  "avg_input_tokens": 222.0,
  "avg_output_tokens": 51.0,
  "p50_latency_ms": 350.0,
  "p95_latency_ms": 800.0
}
```

### POST /register_agent

Register or update agent metadata.

**Request:**
```json
{
  "id": "retriever",
  "description": "Document retrieval via vector search",
  "avg_cost": 0.0008,
  "avg_latency": 420.0
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Agent retriever registered/updated"
}
```

### POST /record_execution

Record an agent execution in the inventory.

**Request:**
```json
{
  "agent_id": "retriever",
  "execution_id": "exec_123",
  "timestamp": "2024-01-15T10:30:00",
  "success": true,
  "runtime_ms": 420.0,
  "input_tokens": 222,
  "output_tokens": 51,
  "total_tokens": 273,
  "cost_usd": 0.0008,
  "error_message": null
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Execution recorded for agent retriever",
  "execution_id": "exec_123"
}
```

### DELETE /agent/{agent_id}

Delete an agent and all its execution records from the inventory.

**Response:**
```json
{
  "status": "success",
  "message": "Agent summarizer-agent and all its records deleted"
}
```

## Usage Examples

### PowerShell

**List all agents:**
```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8001/list_agents" -Method GET
$response | ConvertTo-Json -Depth 10
```

**Get agent usage:**
```powershell
$agentId = "retriever"
$response = Invoke-RestMethod -Uri "http://localhost:8001/usage?agent=$agentId" -Method GET
$response | ConvertTo-Json -Depth 10
```

**Record an execution:**
```powershell
$body = @{
    agent_id = "summarizer-agent"
    execution_id = "exec_123"
    success = $true
    runtime_ms = 1250.5
    input_tokens = 150
    output_tokens = 75
    total_tokens = 225
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8001/record_execution" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json
```

### Python

```python
import requests

# List all agents
response = requests.get("http://localhost:8001/list_agents")
print(response.json())

# Get agent usage
agent_id = "retriever"
response = requests.get(f"http://localhost:8001/usage?agent={agent_id}")
print(response.json())

# Record an execution
execution_data = {
    "agent_id": "summarizer-agent",
    "execution_id": "exec_123",
    "success": True,
    "runtime_ms": 1250.5,
    "input_tokens": 150,
    "output_tokens": 75,
    "total_tokens": 225,
}

response = requests.post(
    "http://localhost:8001/record_execution",
    json=execution_data
)
print(response.json())
```

## Data Storage

Currently, the server uses in-memory storage. All data is lost when the server restarts.

**For production use**, consider:
- SQLite database for small deployments
- PostgreSQL or MySQL for larger deployments
- Redis for high-performance caching
- File-based storage (JSON/CSV) for persistence

## Metrics Tracked

### Agent Metadata (list_agents):
1. **id**: Agent identifier
2. **description**: Human-readable description of the agent
3. **avg_cost**: Average cost per execution (USD)
4. **avg_latency**: Average execution time (milliseconds)

### Usage Statistics (usage endpoint):
1. **total_runs**: Total number of times an agent has been executed
2. **failures**: Number of failed executions
3. **avg_input_tokens**: Average input tokens per execution
4. **avg_output_tokens**: Average output tokens per execution
5. **p50_latency_ms**: 50th percentile (median) latency in milliseconds
6. **p95_latency_ms**: 95th percentile latency in milliseconds

## Use Cases

This server enables:
- **Cost Heatmap per Agent**: Visualize which agents consume the most resources
- **Bottleneck Identification**: Identify slow or failing agents using latency percentiles
- **Introspection and Policy Adjustments**: Make data-driven decisions about agent deployment and optimization

## Integration Example

To integrate with your agent:

```python
import requests
import time
from datetime import datetime

def record_agent_execution(
    agent_id: str,
    success: bool,
    runtime_ms: float,
    input_tokens: int,
    output_tokens: int,
    error_message: str = None
):
    """Record an agent execution to the inventory server"""
    
    execution_data = {
        "agent_id": agent_id,
        "execution_id": f"{agent_id}_{datetime.now().timestamp()}",
        "timestamp": datetime.now().isoformat(),
        "success": success,
        "runtime_ms": runtime_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "error_message": error_message,
    }
    
    try:
        response = requests.post(
            "http://localhost:8001/record_execution",
            json=execution_data,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to record execution: {e}")
        return None

# Usage in your agent
def run_agent(prompt: str):
    start_time = time.time()
    
    try:
        # Your agent logic here
        result = agent.run(prompt)
        
        runtime_ms = (time.time() - start_time) * 1000
        
        # Record successful execution
        record_agent_execution(
            agent_id="summarizer-agent",
            success=True,
            runtime_ms=runtime_ms,
            input_tokens=150,  # Get from actual response
            output_tokens=75,  # Get from actual response
        )
        
        return result
    except Exception as e:
        runtime_ms = (time.time() - start_time) * 1000
        
        # Record failed execution
        record_agent_execution(
            agent_id="summarizer-agent",
            success=False,
            runtime_ms=runtime_ms,
            input_tokens=150,
            output_tokens=0,
            error_message=str(e),
        )
        raise
```

## License

MIT

