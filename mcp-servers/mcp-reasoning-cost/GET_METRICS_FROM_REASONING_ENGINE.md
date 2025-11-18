# Getting Metrics from Vertex AI Reasoning Engine

## Overview

To estimate reasoning costs, you need:
1. **`input_tokens`** and **`output_tokens`** - ✅ Provided by Vertex AI API
2. **`steps`**, **`tool_calls`**, **`tokens_in_trace`** - ❌ You need to track these yourself

## What Vertex AI API Provides

### Token Counts (from API response)

When you call a Vertex AI Reasoning Engine, the API response includes usage metadata:

```python
from google.cloud import aiplatform
import vertexai
from vertexai.preview import reasoning_engines

# Initialize
vertexai.init(project="your-project", location="us-central1")

# Call reasoning engine
response = reasoning_engines.ReasoningEngine("your-engine-id").query(
    query="Your prompt here"
)

# ✅ GET TOKEN COUNTS FROM API
usage_metadata = response.usage_metadata
input_tokens = usage_metadata.prompt_token_count
output_tokens = usage_metadata.candidates_token_count
total_tokens = usage_metadata.total_token_count

print(f"Input tokens: {input_tokens}")
print(f"Output tokens: {output_tokens}")
print(f"Total tokens: {total_tokens}")
```

### Alternative: Using REST API directly

```python
import requests
from google.auth import default
from google.auth.transport.requests import Request

# Get credentials
credentials, _ = default()
credentials.refresh(Request())
access_token = credentials.token

# Call reasoning engine via REST API
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

payload = {
    "query": "Your prompt here"
}

response = requests.post(
    f"https://us-central1-aiplatform.googleapis.com/v1beta1/"
    f"projects/{PROJECT_NUMBER}/locations/us-central1/"
    f"reasoningEngines/{REASONING_ENGINE_ID}:query",
    headers=headers,
    json=payload
)

result = response.json()

# ✅ GET TOKEN COUNTS FROM RESPONSE
usage_metadata = result.get("usageMetadata", {})
input_tokens = usage_metadata.get("promptTokenCount", 0)
output_tokens = usage_metadata.get("candidatesTokenCount", 0)
total_tokens = usage_metadata.get("totalTokenCount", 0)
```

## What You Need to Track Yourself

### 1. Steps (Reasoning Depth)

**Steps** = Number of reasoning iterations/iterations the model went through.

**How to track:**
- If using **multi-step reasoning**, count each reasoning step
- Look for patterns like:
  - `<thinking>...</thinking>` tags (if the model outputs intermediate reasoning)
  - Multiple API calls in a reasoning loop
  - Iteration markers in the response

```python
# Example: Track steps from reasoning trace
def count_reasoning_steps(response_text: str) -> int:
    """Count reasoning steps from response"""
    # Method 1: Count <thinking> tags if model outputs them
    steps = response_text.count("<thinking>")
    
    # Method 2: Count explicit step markers
    # steps = response_text.count("Step ") or response_text.count("Reasoning:")
    
    # Method 3: If using iterative reasoning, count iterations
    # This depends on your reasoning engine implementation
    
    return max(steps, 1)  # At least 1 step
```

### 2. Tool Calls

**Tool Calls** = Number of times the model called external tools/functions during reasoning.

**How to track:**
- If using **function calling**, count function invocations
- Count API calls made by the reasoning engine
- Count tool/framework calls

```python
# Example: Track tool calls from function calling
def count_tool_calls(response) -> int:
    """Count tool calls from response"""
    tool_calls = 0
    
    # Method 1: Count function calls if using Vertex AI function calling
    if hasattr(response, 'function_calls'):
        tool_calls = len(response.function_calls)
    
    # Method 2: Count tool invocations in the response
    # If your reasoning engine logs tool calls, extract from logs
    
    # Method 3: Track during execution
    # Increment counter each time a tool is invoked
    
    return tool_calls
```

### 3. Tokens in Trace

**Tokens in Trace** = Total tokens used across all reasoning steps (including intermediate reasoning).

**How to calculate:**
```python
# Option 1: Use total tokens from API if it includes all reasoning
tokens_in_trace = usage_metadata.total_token_count

# Option 2: Sum tokens from all reasoning steps
# If you have multiple API calls for multi-step reasoning:
tokens_in_trace = sum(step_response.usage_metadata.total_token_count 
                      for step_response in all_step_responses)

# Option 3: Estimate from response length
from vertexai.generative_models import Tokenizer
tokens_in_trace = Tokenizer().count_tokens(full_reasoning_trace)
```

## Complete Example: Tracking All Metrics

```python
from google.cloud import aiplatform
import vertexai
from vertexai.preview import reasoning_engines

def track_reasoning_metrics(engine_id: str, query: str):
    """Track all metrics needed for cost estimation"""
    
    # Track metrics
    steps = 0
    tool_calls = 0
    all_responses = []
    
    # Call reasoning engine (simplified - adjust based on your implementation)
    response = reasoning_engines.ReasoningEngine(engine_id).query(query=query)
    
    # ✅ Get token counts from API
    usage_metadata = response.usage_metadata
    input_tokens = usage_metadata.prompt_token_count
    output_tokens = usage_metadata.candidates_token_count
    total_tokens = usage_metadata.total_token_count
    
    # ❌ Track steps - depends on your reasoning engine
    # If multi-step reasoning is explicit in response:
    response_text = response.text
    steps = count_reasoning_steps(response_text)
    
    # ❌ Track tool calls - depends on function calling usage
    if hasattr(response, 'function_calls'):
        tool_calls = len(response.function_calls)
    
    # ❌ Tokens in trace - use total or sum all steps
    tokens_in_trace = total_tokens  # Or sum from all steps
    
    return {
        "steps": steps,
        "tool_calls": tool_calls,
        "tokens_in_trace": tokens_in_trace,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": "gemini-2.5-pro"  # Or get from engine config
    }
```

## Integration with Cost Estimation

```python
import requests

# Get metrics from reasoning engine
metrics = track_reasoning_metrics("your-engine-id", "Your prompt")

# Estimate cost
cost_estimate = requests.post(
    "http://localhost:8002/estimate",
    json={
        "trace": {
            "steps": metrics["steps"],
            "tool_calls": metrics["tool_calls"],
            "tokens_in_trace": metrics["tokens_in_trace"],
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "model": metrics["model"]
        }
    }
).json()

print(f"Cost: ${cost_estimate['estimated_cost_usd']}")
print(f"Cost Score: {cost_estimate['cost_score']}")
```

## Key Takeaways

1. **✅ Use Vertex AI API for**: `input_tokens`, `output_tokens` (from `usage_metadata`)
2. **❌ Track yourself**: `steps`, `tool_calls`, `tokens_in_trace` (depends on your reasoning implementation)
3. **Steps and tool calls** depend on how your reasoning engine works:
   - Multi-step reasoning: Count iterations/steps
   - Function calling: Count function invocations
   - Custom tools: Count tool calls in your framework
4. **Tokens in trace** can often use `total_token_count` from API, or sum tokens from all reasoning steps

## If Using Vertex AI Reasoning Engine SDK

The SDK may provide additional metadata. Check the response object:

```python
response = reasoning_engine.query(query="...")

# Check what's available
print(dir(response))
print(response.__dict__)

# Look for:
# - reasoning_steps (if available)
# - tool_invocations (if available)
# - full_trace (if available)
```

## Recommendation

1. **Start simple**: Use `total_token_count` for `tokens_in_trace`
2. **Set steps = 1** initially, then refine based on your reasoning pattern
3. **Set tool_calls = 0** initially, then add if you use function calling
4. **Refine over time** as you understand your reasoning engine's behavior

