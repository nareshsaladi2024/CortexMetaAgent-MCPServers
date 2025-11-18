# ReasoningCost MCP Server

Remote MCP (Model Control Protocol) server for estimating reasoning costs based on chain-of-thought metrics.

## Features

- **Reasoning Cost Estimation**: Analyze reasoning traces to calculate cost scores
- **Chain-of-Thought Analysis**: Detect runaway reasoning patterns
- **Expansion Factor Calculation**: Measure prompt length growth
- **Tool Invocation Tracking**: Account for tool call overhead
- **Cost Optimization**: Identify expensive reasoning paths

## Use Cases

This server is used for:
- **Detecting Runaway Chain-of-Thought**: Identify when reasoning becomes too deep or verbose
- **Penalizing Expensive Reasoning Paths**: Guide agent decisions toward cost-efficient reasoning
- **Evaluating Reasoning Compression Strategies**: Measure effectiveness of reasoning optimization techniques

## Setup

### 1. Install Dependencies

```powershell
cd "C:\AI Agents\CortexEvalAI\mcp-servers\mcp-reasoning-cost"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

Create a `.env` file:

```env
PORT=8002
```

Or set it in PowerShell:

```powershell
$env:PORT = 8002
```

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
uvicorn server:app --host 0.0.0.0 --port 8002 --reload
```

The server will start on `http://localhost:8002`

## API Endpoints

### POST /estimate

Estimate reasoning cost based on trace metrics.

**Request:**
```json
{
  "trace": {
    "steps": 8,
    "tool_calls": 3,
    "tokens_in_trace": 1189
  }
}
```

**Response:**
```json
{
  "reasoning_depth": 8,
  "tool_invocations": 3,
  "expansion_factor": 1.74,
  "cost_score": 0.88
}
```

**Response Fields:**
- `reasoning_depth`: Number of reasoning steps (same as input steps)
- `tool_invocations`: Number of tool invocations (same as input tool_calls)
- `expansion_factor`: Ratio of actual tokens to expected tokens (measures verbosity)
- `cost_score`: Combined cost score (0.0 = minimal, 1.0+ = expensive)

### POST /estimate_multiple

Estimate reasoning cost for multiple traces (batch processing).

**Request:**
```json
{
  "traces": [
    {
      "steps": 8,
      "tool_calls": 3,
      "tokens_in_trace": 1189
    },
    {
      "steps": 5,
      "tool_calls": 1,
      "tokens_in_trace": 650
    }
  ]
}
```

**Response:**
```json
{
  "estimates": [
    {
      "reasoning_depth": 8,
      "tool_invocations": 3,
      "expansion_factor": 1.74,
      "cost_score": 0.88
    },
    {
      "reasoning_depth": 5,
      "tool_invocations": 1,
      "expansion_factor": 1.30,
      "cost_score": 0.45
    }
  ],
  "count": 2
}
```

## Usage Examples

### PowerShell

**Estimate reasoning cost:**
```powershell
$body = @{
    trace = @{
        steps = 8
        tool_calls = 3
        tokens_in_trace = 1189
    }
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod -Uri "http://localhost:8002/estimate" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 10
```

### Python

```python
import requests

# Estimate reasoning cost
trace_data = {
    "trace": {
        "steps": 8,
        "tool_calls": 3,
        "tokens_in_trace": 1189
    }
}

response = requests.post(
    "http://localhost:8002/estimate",
    json=trace_data
)

result = response.json()
print(f"Reasoning Depth: {result['reasoning_depth']}")
print(f"Tool Invocations: {result['tool_invocations']}")
print(f"Expansion Factor: {result['expansion_factor']}")
print(f"Cost Score: {result['cost_score']}")
```

### cURL

```bash
curl -X POST http://localhost:8002/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "trace": {
      "steps": 8,
      "tool_calls": 3,
      "tokens_in_trace": 1189
    }
  }'
```

## Cost Score Calculation

The cost score is calculated using three factors:

1. **Reasoning Depth (40% weight)**: More steps = higher cost
   - Normalized: steps / 20 * 0.4 (max 0.4)

2. **Tool Invocations (30% weight)**: Each tool call adds overhead
   - Normalized: tool_calls / 10 * 0.3 (max 0.3)

3. **Expansion Factor (30% weight)**: Verbose reasoning increases cost
   - Normalized: (expansion_factor - 1.0) / 2.0 * 0.3 (max 0.3)

**Score Interpretation:**
- `0.0 - 0.3`: Low cost (efficient reasoning)
- `0.3 - 0.6`: Medium cost (normal reasoning)
- `0.6 - 1.0`: High cost (expensive reasoning)
- `1.0+`: Very high cost (runaway reasoning detected)

## Expansion Factor

The expansion factor measures how much the prompt grew relative to expected size:

```
expansion_factor = tokens_in_trace / (steps * expected_tokens_per_step)
```

**Interpretation:**
- `1.0`: Normal verbosity
- `1.5`: Moderately verbose
- `2.0+`: Very verbose (potential runaway)

## Integration Example

To integrate with your reasoning engine:

```python
import requests
from typing import Dict, Any

def estimate_reasoning_cost(
    steps: int,
    tool_calls: int,
    tokens_in_trace: int,
    server_url: str = "http://localhost:8002"
) -> Dict[str, Any]:
    """Estimate reasoning cost using the MCP server"""
    
    trace_data = {
        "trace": {
            "steps": steps,
            "tool_calls": tool_calls,
            "tokens_in_trace": tokens_in_trace
        }
    }
    
    try:
        response = requests.post(
            f"{server_url}/estimate",
            json=trace_data,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to estimate reasoning cost: {e}")
        return None

# Usage in reasoning engine
def run_reasoning(prompt: str):
    steps = 0
    tool_calls = 0
    tokens = 0
    
    # Your reasoning logic here
    # Track steps, tool_calls, and tokens...
    
    # Estimate cost
    cost_estimate = estimate_reasoning_cost(steps, tool_calls, tokens)
    
    if cost_estimate and cost_estimate["cost_score"] > 1.0:
        print("WARNING: Runaway reasoning detected!")
        # Implement compression or early termination
    
    return result
```

## Error Handling

The server returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid input)
- `500`: Server error

## License

MIT

