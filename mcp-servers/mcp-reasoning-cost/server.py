"""
MCP Server: ReasoningCost
Remote server for estimating reasoning costs based on chain-of-thought metrics
"""

import json
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import math

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="ReasoningCost MCP Server", version="1.0.0")

# Add CORS middleware for remote access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base constants for cost calculation
# These represent baseline values for "normal" reasoning
BASE_TOKENS = 500  # Baseline token count for standard reasoning
BASE_STEPS = 5  # Baseline number of reasoning steps
BASE_TOOL_CALLS = 1  # Baseline number of tool calls

# LLM Pricing per million tokens (default: Gemini 2.5 Pro on Vertex AI)
# Prices for prompts up to 200,000 tokens
# Can be overridden via environment variables or request
DEFAULT_INPUT_TOKEN_PRICE_PER_MILLION = float(os.getenv("LLM_INPUT_TOKEN_PRICE_PER_M", "1.25"))  # $1.25 per million
DEFAULT_OUTPUT_TOKEN_PRICE_PER_MILLION = float(os.getenv("LLM_OUTPUT_TOKEN_PRICE_PER_M", "10.00"))  # $10.00 per million

# Model pricing presets (per million tokens)
MODEL_PRICING = {
    "gemini-2.5-pro": {
        "input": 1.25,  # $1.25 per million tokens
        "output": 10.00,  # $10.00 per million tokens
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00,
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "gpt-4": {
        "input": 10.00,
        "output": 30.00,
    },
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
    },
    "gpt-3.5-turbo": {
        "input": 0.50,
        "output": 1.50,
    },
}


class Trace(BaseModel):
    """Model for reasoning trace"""
    steps: int
    tool_calls: int
    tokens_in_trace: int
    input_tokens: Optional[int] = None  # Input tokens for LLM cost calculation
    output_tokens: Optional[int] = None  # Output tokens for LLM cost calculation
    model: Optional[str] = None  # Model name for pricing lookup


class EstimateRequest(BaseModel):
    """Request model for estimate endpoint"""
    trace: Trace


class EstimateResponse(BaseModel):
    """Response model for estimate endpoint"""
    reasoning_depth: int
    tool_invocations: int
    expansion_factor: float
    cost_score: float
    estimated_cost_usd: Optional[float] = None  # Estimated LLM cost in USD
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    model: Optional[str] = None
    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None


def calculate_expansion_factor(tokens_in_trace: int, steps: int) -> float:
    """
    Calculate the expansion factor (how much the prompt grew)
    
    Expansion factor measures prompt length growth relative to base reasoning.
    Higher values indicate more verbose reasoning.
    
    Args:
        tokens_in_trace: Total tokens in the reasoning trace
        steps: Number of reasoning steps
        
    Returns:
        float: Expansion factor (typically 1.0-3.0)
    """
    if steps == 0:
        return 1.0
    
    # Calculate expected tokens for this many steps
    # Each step typically adds ~100-200 tokens
    expected_tokens_per_step = BASE_TOKENS / BASE_STEPS
    expected_tokens = steps * expected_tokens_per_step
    
    if expected_tokens == 0:
        return 1.0
    
    # Expansion factor is ratio of actual to expected tokens
    expansion = tokens_in_trace / expected_tokens
    
    # Normalize to reasonable range (1.0-3.0 typically)
    # Cap at 3.0 to avoid extreme values
    return min(round(expansion, 2), 3.0)


def calculate_llm_cost(
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate actual LLM cost in USD based on token usage
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name for pricing lookup (optional)
        
    Returns:
        Dictionary with cost breakdown
    """
    if input_tokens is None and output_tokens is None:
        return {
            "estimated_cost_usd": None,
            "input_cost_usd": None,
            "output_cost_usd": None,
            "model": model
        }
    
    # Get pricing for model or use defaults
    if model and model in MODEL_PRICING:
        input_price_per_m = MODEL_PRICING[model]["input"]
        output_price_per_m = MODEL_PRICING[model]["output"]
    else:
        input_price_per_m = DEFAULT_INPUT_TOKEN_PRICE_PER_MILLION
        output_price_per_m = DEFAULT_OUTPUT_TOKEN_PRICE_PER_MILLION
    
    # Calculate costs (convert per million to per token)
    input_cost = 0.0
    output_cost = 0.0
    
    if input_tokens:
        input_cost = (input_tokens / 1_000_000) * input_price_per_m
    
    if output_tokens:
        output_cost = (output_tokens / 1_000_000) * output_price_per_m
    
    total_cost = input_cost + output_cost
    
    return {
        "estimated_cost_usd": round(total_cost, 6),
        "input_cost_usd": round(input_cost, 6) if input_tokens else None,
        "output_cost_usd": round(output_cost, 6) if output_tokens else None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model or "default"
    }


def calculate_cost_score(
    steps: int,
    tool_calls: int,
    tokens_in_trace: int,
    expansion_factor: float
) -> float:
    """
    Calculate a cost score (0.0-1.0+) representing reasoning cost
    
    The score combines multiple factors:
    - Reasoning depth (more steps = higher cost)
    - Tool invocations (each tool call adds overhead)
    - Token expansion (more verbose reasoning = higher cost)
    
    Args:
        steps: Number of reasoning steps
        tool_calls: Number of tool invocations
        tokens_in_trace: Total tokens in trace
        expansion_factor: Token expansion factor
        
    Returns:
        float: Cost score (0.0 = minimal cost, 1.0+ = expensive)
    """
    # Normalize steps (0-20 range maps to 0-0.4 score)
    steps_score = min(steps / 20.0, 1.0) * 0.4
    
    # Normalize tool calls (0-10 range maps to 0-0.3 score)
    tool_score = min(tool_calls / 10.0, 1.0) * 0.3
    
    # Expansion factor contributes (1.0-3.0 maps to 0-0.3 score)
    expansion_score = min((expansion_factor - 1.0) / 2.0, 1.0) * 0.3
    
    # Combine scores
    total_score = steps_score + tool_score + expansion_score
    
    # Round to 2 decimal places
    return round(total_score, 2)


@app.post("/estimate", response_model=EstimateResponse)
async def estimate_reasoning_cost(request: EstimateRequest) -> EstimateResponse:
    """
    Estimate reasoning cost based on trace metrics
    
    This endpoint analyzes reasoning traces to detect:
    - Runaway chain-of-thought (high steps, high expansion)
    - Expensive reasoning paths (high tool calls, high tokens)
    - Opportunities for reasoning compression
    
    Args:
        request: EstimateRequest containing trace metrics
        
    Returns:
        EstimateResponse with cost analysis
    """
    try:
        trace = request.trace
        
        # Validate inputs
        if trace.steps < 0:
            raise HTTPException(status_code=400, detail="Steps must be non-negative")
        if trace.tool_calls < 0:
            raise HTTPException(status_code=400, detail="Tool calls must be non-negative")
        if trace.tokens_in_trace < 0:
            raise HTTPException(status_code=400, detail="Tokens in trace must be non-negative")
        
        # Calculate metrics
        reasoning_depth = trace.steps
        tool_invocations = trace.tool_calls
        expansion_factor = calculate_expansion_factor(trace.tokens_in_trace, trace.steps)
        cost_score = calculate_cost_score(
            trace.steps,
            trace.tool_calls,
            trace.tokens_in_trace,
            expansion_factor
        )
        
        # Calculate actual LLM cost if tokens provided
        cost_breakdown = calculate_llm_cost(
            trace.input_tokens,
            trace.output_tokens,
            trace.model
        )
        
        return EstimateResponse(
            reasoning_depth=reasoning_depth,
            tool_invocations=tool_invocations,
            expansion_factor=expansion_factor,
            cost_score=cost_score,
            estimated_cost_usd=cost_breakdown["estimated_cost_usd"],
            input_tokens=cost_breakdown["input_tokens"],
            output_tokens=cost_breakdown["output_tokens"],
            model=cost_breakdown["model"],
            input_cost_usd=cost_breakdown["input_cost_usd"],
            output_cost_usd=cost_breakdown["output_cost_usd"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error estimating reasoning cost: {str(e)}")


@app.post("/estimate_multiple")
async def estimate_multiple_traces(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estimate reasoning cost for multiple traces (batch processing)
    
    Args:
        request: Dictionary with "traces" key containing list of traces
        
    Returns:
        Dictionary with list of estimates
    """
    try:
        traces = request.get("traces", [])
        
        if not isinstance(traces, list):
            raise HTTPException(status_code=400, detail="Traces must be a list")
        
        estimates = []
        for trace_data in traces:
            trace = Trace(**trace_data)
            estimate_request = EstimateRequest(trace=trace)
            estimate = await estimate_reasoning_cost(estimate_request)
            # Support both Pydantic v1 and v2
            if hasattr(estimate, "model_dump"):
                estimates.append(estimate.model_dump())
            else:
                estimates.append(estimate.dict())
        
        return {
            "estimates": estimates,
            "count": len(estimates)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error estimating multiple traces: {str(e)}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "ReasoningCost MCP Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "estimate": "POST /estimate",
            "estimate_multiple": "POST /estimate_multiple",
        },
        "description": "Estimates reasoning costs based on chain-of-thought metrics",
        "use_cases": [
            "Detecting runaway chain-of-thought",
            "Penalizing expensive reasoning paths",
            "Evaluating reasoning compression strategies"
        ]
    }


@app.post("/")
async def mcp_endpoint(request: Request):
    """
    MCP protocol endpoint (JSON-RPC 2.0)
    Handles MCP protocol messages for MCP Inspector and other MCP clients
    """
    try:
        body = await request.json()
        
        # Extract JSON-RPC fields
        jsonrpc = body.get("jsonrpc", "2.0")
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")
        
        # Handle different MCP methods
        if method == "initialize":
            response = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "reasoning-cost",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "estimate_reasoning_cost",
                            "description": "Estimate reasoning cost based on trace metrics. Returns both relative cost_score and actual LLM cost in USD if input/output tokens provided.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "trace": {
                                        "type": "object",
                                        "properties": {
                                            "steps": {"type": "integer", "description": "Number of reasoning steps"},
                                            "tool_calls": {"type": "integer", "description": "Number of tool invocations"},
                                            "tokens_in_trace": {"type": "integer", "description": "Total tokens in the reasoning trace"},
                                            "input_tokens": {"type": "integer", "description": "Input tokens for LLM cost calculation (optional)"},
                                            "output_tokens": {"type": "integer", "description": "Output tokens for LLM cost calculation (optional)"},
                                            "model": {"type": "string", "description": "Model name for pricing (e.g., 'gemini-2.5-pro', 'gpt-4'). Optional, defaults to gemini-2.5-pro pricing."}
                                        },
                                        "required": ["steps", "tool_calls", "tokens_in_trace"]
                                    }
                                },
                                "required": ["trace"]
                            }
                        },
                        {
                            "name": "estimate_multiple_traces",
                            "description": "Estimate reasoning cost for multiple traces (batch processing)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "traces": {
                                        "type": "array",
                                        "description": "List of trace objects",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "steps": {"type": "integer"},
                                                "tool_calls": {"type": "integer"},
                                                "tokens_in_trace": {"type": "integer"}
                                            },
                                            "required": ["steps", "tool_calls", "tokens_in_trace"]
                                        }
                                    }
                                },
                                "required": ["traces"]
                            }
                        }
                    ]
                }
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # Helper function to serialize result
            def serialize_result(result):
                """Serialize result to JSON string, handling Pydantic models"""
                if hasattr(result, "model_dump"):
                    return json.dumps(result.model_dump(), indent=2)
                elif hasattr(result, "dict"):
                    return json.dumps(result.dict(), indent=2)
                else:
                    return json.dumps(result, indent=2, default=str)
            
            # Route to appropriate handler
            if tool_name == "estimate_reasoning_cost":
                trace_data = tool_args.get("trace")
                if not trace_data:
                    raise HTTPException(status_code=400, detail="trace parameter is required")
                trace = Trace(**trace_data)
                estimate_request = EstimateRequest(trace=trace)
                result = await estimate_reasoning_cost(estimate_request)
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": serialize_result(result)
                            }
                        ]
                    }
                }
            elif tool_name == "estimate_multiple_traces":
                traces = tool_args.get("traces")
                if not traces:
                    raise HTTPException(status_code=400, detail="traces parameter is required")
                result = await estimate_multiple_traces({"traces": traces})
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": serialize_result(result)
                            }
                        ]
                    }
                }
            else:
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {tool_name}"
                    }
                }
        else:
            response = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": body.get("id") if "body" in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

