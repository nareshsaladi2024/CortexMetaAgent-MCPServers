"""
MCP Server: TokenStats
Remote server for pulling token usage statistics from Gemini Flash 2.5
"""

import json
import os
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="TokenStats MCP Server", version="1.0.0")

# Add CORS middleware for remote access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
API_KEY = os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("WARNING: GOOGLE_API_KEY environment variable is not set.")
    print("Token counting will fail. Set it with: export GOOGLE_API_KEY='your-api-key'")

# Gemini API Pricing (per million tokens) - Standard tier
# Reference: https://ai.google.dev/gemini-api/docs/pricing
MODEL_PRICING = {
    "gemini-2.5-pro": {
        "input": 1.25,  # $1.25/M tokens (prompts <= 200k tokens)
        "input_extended": 2.50,  # $2.50/M tokens (prompts > 200k tokens)
        "output": 10.00,  # $10.00/M tokens (outputs <= 200k tokens, including thinking tokens)
        "output_extended": 15.00,  # $15.00/M tokens (outputs > 200k tokens)
        "threshold": 200_000,  # Token threshold for extended pricing
    },
    "gemini-2.5-flash": {
        "input": 0.30,  # $0.30/M tokens (text/image/video)
        "input_audio": 1.00,  # $1.00/M tokens (audio)
        "output": 2.50,  # $2.50/M tokens (including thinking tokens)
    },
    "gemini-2.5-flash-preview-09-2025": {
        "input": 0.30,
        "input_audio": 1.00,
        "output": 2.50,
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "input_extended": 2.50,
        "output": 5.00,
        "output_extended": 7.50,
        "threshold": 200_000,
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "gemini-1.5-flash-8b": {
        "input": 0.0375,
        "output": 0.15,
    },
}

# Default pricing (Gemini 2.5 Flash)
DEFAULT_INPUT_COST_PER_MILLION = MODEL_PRICING["gemini-2.5-flash"]["input"]
DEFAULT_OUTPUT_COST_PER_MILLION = MODEL_PRICING["gemini-2.5-flash"]["output"]

# Model context limits
MAX_INPUT_TOKENS = 1048576  # 1M tokens for Gemini 2.5 Flash
MAX_OUTPUT_TOKENS = 65536   # 64K tokens for Gemini 2.5 Flash


class TokenizeRequest(BaseModel):
    """Request model for tokenize endpoint"""
    model: str  # Model name (e.g., gemini-2.5-pro, gemini-2.5-flash)
    prompt: str  # Input text (prompt + context)
    generate: Optional[bool] = False  # If True, make actual API call to get real token counts and costs
    context_cache_tokens: Optional[int] = 0  # Tokens in context cache (if used)
    context_cache_storage_hours: Optional[float] = 0.0  # Hours of context cache storage (if used)


class TokenStatsResponse(BaseModel):
    """Response model for token statistics"""
    input_tokens: int  # Input tokens (prompt + context)
    estimated_output_tokens: Optional[int] = None  # Estimated output tokens
    actual_output_tokens: Optional[int] = None  # Actual output tokens (response + thinking tokens) from API call
    estimated_cost_usd: float  # Estimated total cost
    actual_cost_usd: Optional[float] = None  # Actual total cost from API call
    input_cost_usd: Optional[float] = None  # Input cost: (input_tokens / 1M) × input_price_per_1M
    output_cost_usd: Optional[float] = None  # Output cost: (output_tokens / 1M) × output_price_per_1M
    context_cache_cost_usd: Optional[float] = None  # Context cache storage cost (if applicable)
    model: str  # Model name used
    pricing_tier: Optional[str] = None  # "standard" or "extended" (>200k tokens threshold)
    input_price_per_m: Optional[float] = None  # Input price per million tokens used
    output_price_per_m: Optional[float] = None  # Output price per million tokens used
    max_tokens_remaining: int  # Remaining tokens in context window
    compression_ratio: Optional[float] = None  # Output/input ratio


def get_model_pricing(model_name: str) -> Dict[str, float]:
    """
    Get pricing for a specific model
    
    Args:
        model_name: The model name
        
    Returns:
        Dictionary with input and output pricing per million tokens
    """
    # Normalize model name
    model_key = model_name.lower()
    
    # Try exact match first
    if model_key in MODEL_PRICING:
        pricing = MODEL_PRICING[model_key]
        return {
            "input": pricing.get("input", DEFAULT_INPUT_COST_PER_MILLION),
            "output": pricing.get("output", DEFAULT_OUTPUT_COST_PER_MILLION),
            "input_extended": pricing.get("input_extended"),
            "output_extended": pricing.get("output_extended"),
            "threshold": pricing.get("threshold", 200_000),
        }
    
    # Try partial match
    for key, pricing in MODEL_PRICING.items():
        if key in model_key or model_key in key:
            return {
                "input": pricing.get("input", DEFAULT_INPUT_COST_PER_MILLION),
                "output": pricing.get("output", DEFAULT_OUTPUT_COST_PER_MILLION),
                "input_extended": pricing.get("input_extended"),
                "output_extended": pricing.get("output_extended"),
                "threshold": pricing.get("threshold", 200_000),
            }
    
    # Default to Gemini 2.5 Flash
    return {
        "input": DEFAULT_INPUT_COST_PER_MILLION,
        "output": DEFAULT_OUTPUT_COST_PER_MILLION,
        "input_extended": None,
        "output_extended": None,
        "threshold": 200_000,
    }


def calculate_cost(
    input_tokens: int, 
    output_tokens: int, 
    model_name: str = "gemini-2.5-flash",
    context_cache_storage_hours: float = 0.0,
    context_cache_tokens: int = 0
) -> Dict[str, float]:
    """
    Calculate actual cost based on token usage following Gemini API pricing model
    
    Formula: Cost = (input_tokens / 1,000,000) × input_cost_per_1M + 
                   (output_tokens / 1,000,000) × output_cost_per_1M + 
                   any extra fees (e.g., context caching storage)
    
    Args:
        input_tokens: Number of input tokens (prompt + context)
        output_tokens: Number of output tokens (response + thinking tokens)
        model_name: The model name
        context_cache_storage_hours: Hours of context cache storage (if used)
        context_cache_tokens: Number of tokens in context cache (if used)
        
    Returns:
        Dictionary with cost breakdown
    """
    pricing = get_model_pricing(model_name)
    threshold = pricing.get("threshold", 200_000)
    
    # Step 1: Calculate input cost
    # Check if extended pricing applies (>200k tokens threshold)
    if pricing.get("input_extended") and input_tokens > threshold:
        input_price_per_m = pricing["input_extended"]
        pricing_tier = "extended"
    else:
        input_price_per_m = pricing["input"]
        pricing_tier = "standard"
    
    # Formula: (input_tokens / 1,000,000) × input_cost_per_1M
    input_cost = (input_tokens / 1_000_000) * input_price_per_m
    
    # Step 2: Calculate output cost
    # Check if extended pricing applies (>200k tokens threshold)
    if pricing.get("output_extended") and output_tokens > threshold:
        output_price_per_m = pricing["output_extended"]
    else:
        output_price_per_m = pricing["output"]
    
    # Formula: (output_tokens / 1,000,000) × output_cost_per_1M
    output_cost = (output_tokens / 1_000_000) * output_price_per_m
    
    # Step 3: Calculate context caching costs (if applicable)
    # Context caching storage: typically $4.50 / 1,000,000 tokens per hour
    context_cache_cost = 0.0
    if context_cache_storage_hours > 0 and context_cache_tokens > 0:
        # Storage cost: tokens × hours × rate per 1M tokens per hour
        context_cache_cost = (context_cache_tokens / 1_000_000) * context_cache_storage_hours * 4.50
    
    # Step 4: Total cost = input + output + extra fees
    total_cost = input_cost + output_cost + context_cache_cost
    
    return {
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "context_cache_cost_usd": round(context_cache_cost, 6) if context_cache_cost > 0 else None,
        "total_cost_usd": round(total_cost, 6),
        "input_price_per_m": input_price_per_m,
        "output_price_per_m": output_price_per_m,
        "pricing_tier": pricing_tier,
        "threshold": threshold,
    }


def count_tokens_with_gemini(
    prompt: str, 
    model_name: str = "gemini-2.5-flash", 
    generate: bool = False,
    context_cache_tokens: int = 0,
    context_cache_storage_hours: float = 0.0
) -> Dict[str, Any]:
    """
    Count tokens using Gemini API and optionally generate response
    
    Workflow:
    1. Choose model name (e.g., gemini-2.5-pro, gemini-2.5-flash)
    2. Get input tokens (prompt + context) and output tokens (response + thinking tokens)
    3. Calculate cost: (input_tokens / 1,000,000) × input_cost_per_1M + 
                       (output_tokens / 1,000,000) × output_cost_per_1M + extra fees
    
    Args:
        prompt: The input text to tokenize (prompt + context)
        model_name: The Gemini model to use
        generate: If True, make actual API call to get real token counts and costs
        context_cache_tokens: Number of tokens in context cache (if used)
        context_cache_storage_hours: Hours of context cache storage (if used)
        
    Returns:
        Dictionary containing token count information and costs
    """
    try:
        # Step 1: Check API key is configured
        if not API_KEY:
            raise HTTPException(
                status_code=400,
                detail="GOOGLE_API_KEY environment variable is not set. Please set it to use token counting."
            )
        
        # Step 2: Get the model - Initialize as None first
        model = None
        
        try:
            # Ensure genai is configured (reconfigure if needed)
            if not API_KEY:
                raise HTTPException(
                    status_code=400,
                    detail="GOOGLE_API_KEY environment variable is not set. Please set it to use token counting."
                )
            
            # Configure genai with API key
            genai.configure(api_key=API_KEY)
            
            # Verify configuration worked
            if not hasattr(genai, 'GenerativeModel'):
                raise HTTPException(
                    status_code=500,
                    detail="genai.GenerativeModel not available. Check google-generativeai installation."
                )
            
            # Create model with explicit error checking
            try:
                model = genai.GenerativeModel(model_name)
                print(f"DEBUG: Model created - type: {type(model)}, is None: {model is None}")  # Debug output
            except AttributeError as attr_err:
                raise HTTPException(
                    status_code=500,
                    detail=f"AttributeError creating model '{model_name}': {str(attr_err)}. Make sure google-generativeai is installed and GOOGLE_API_KEY is set."
                )
            except ValueError as val_err:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid model name '{model_name}': {str(val_err)}. Use a valid Gemini model name like 'gemini-2.5-flash'."
                )
            except Exception as model_create_err:
                error_msg = str(model_create_err) if str(model_create_err) else type(model_create_err).__name__
                raise HTTPException(
                    status_code=500,
                    detail=f"Exception creating model '{model_name}': {error_msg}. Check GOOGLE_API_KEY and model name."
                )
            
            # Verify model was created successfully
            if model is None:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create model '{model_name}'. Model object is None after creation. This may indicate an API key or model name issue."
                )
                
            # Verify model has required methods before using it
            if not hasattr(model, 'count_tokens'):
                raise HTTPException(
                    status_code=500,
                    detail=f"Model '{model_name}' does not have 'count_tokens' method. Model type: {type(model)}. This may indicate an API library version issue."
                )
                
        except HTTPException:
            raise
        except Exception as model_error:
            error_msg = str(model_error) if str(model_error) else type(model_error).__name__
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error initializing model '{model_name}': {error_msg}. Check that GOOGLE_API_KEY is set correctly and valid."
            )
        
        # Step 3: Count input tokens (prompt + context)
        # Final validation before calling count_tokens
        if model is None:
            raise HTTPException(
                status_code=500,
                detail="Model object is None before count_tokens call. This should not happen."
            )
        
        if not hasattr(model, 'count_tokens'):
            raise HTTPException(
                status_code=500,
                detail=f"Model object does not have 'count_tokens' method. Model type: {type(model)}."
            )
        
        try:
            result = model.count_tokens(prompt)
            input_tokens = result.total_tokens  # Total input tokens (prompt + any context)
        except Exception as count_error:
            error_msg = str(count_error) if str(count_error) else type(count_error).__name__
            raise HTTPException(
                status_code=400,
                detail=f"Failed to count tokens: {error_msg}. Check that GOOGLE_API_KEY is set and valid."
            )
        
        actual_output_tokens = None
        actual_cost_usd = None
        output_cost_usd = None
        input_cost_usd = None
        cost_breakdown = None
        
        # Step 4: If generate is True, make actual API call to get real output tokens
        if generate:
            try:
                response = model.generate_content(prompt)
                
                # Get actual token counts from API response
                # Output tokens include: response + thinking tokens (if applicable)
                if hasattr(response, 'usage_metadata'):
                    actual_output_tokens = response.usage_metadata.candidates_token_count
                    # Verify input tokens match (should be same or close)
                    api_input_tokens = response.usage_metadata.prompt_token_count
                    total_api_tokens = response.usage_metadata.total_token_count
                    
                # Calculate actual cost using the formula
                cost_breakdown = calculate_cost(
                    input_tokens=input_tokens,
                    output_tokens=actual_output_tokens or 0,
                    model_name=model_name,
                    context_cache_storage_hours=context_cache_storage_hours,
                    context_cache_tokens=context_cache_tokens
                )
                input_cost_usd = cost_breakdown["input_cost_usd"]
                output_cost_usd = cost_breakdown["output_cost_usd"]
                actual_cost_usd = cost_breakdown["total_cost_usd"]
                
            except Exception as gen_error:
                # If generation fails, continue with estimation only
                error_msg = str(gen_error) or type(gen_error).__name__ or "Unknown error"
                # Don't raise, just log that we can't get actual tokens
                actual_output_tokens = None
        
        # Step 5: Estimate output tokens if we don't have actual count
        # Typically 20-50% of input for summaries, using conservative 40%
        estimated_output_tokens = int(input_tokens * 0.4) if not actual_output_tokens else None
        
        # Ensure estimated output doesn't exceed max
        if estimated_output_tokens and estimated_output_tokens > MAX_OUTPUT_TOKENS:
            estimated_output_tokens = MAX_OUTPUT_TOKENS
        
        # Step 6: Calculate cost using the formula
        # Cost = (input_tokens / 1,000,000) × input_cost_per_1M + 
        #        (output_tokens / 1,000,000) × output_cost_per_1M + extra fees
        if actual_cost_usd is None:
            # Use estimated output tokens for cost calculation
            output_tokens_for_cost = estimated_output_tokens or 0
            cost_breakdown = calculate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens_for_cost,
                model_name=model_name,
                context_cache_storage_hours=context_cache_storage_hours,
                context_cache_tokens=context_cache_tokens
            )
            estimated_cost_usd = cost_breakdown["total_cost_usd"]
            if input_cost_usd is None:
                input_cost_usd = cost_breakdown["input_cost_usd"]
            if output_cost_usd is None:
                output_cost_usd = cost_breakdown["output_cost_usd"]
        else:
            # Use actual cost as estimated if we have it
            estimated_cost_usd = actual_cost_usd
        
        # Calculate remaining tokens
        max_tokens_remaining = MAX_INPUT_TOKENS - input_tokens
        
        # Calculate compression ratio (output/input)
        compression_ratio = None
        if actual_output_tokens:
            compression_ratio = round(actual_output_tokens / input_tokens, 2) if input_tokens > 0 else 0
        elif estimated_output_tokens:
            compression_ratio = round(estimated_output_tokens / input_tokens, 2) if input_tokens > 0 else 0
        
        return {
            "input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "actual_output_tokens": actual_output_tokens,
            "estimated_cost_usd": round(estimated_cost_usd, 6),
            "actual_cost_usd": round(actual_cost_usd, 6) if actual_cost_usd else None,
            "input_cost_usd": input_cost_usd,
            "output_cost_usd": output_cost_usd,
            "context_cache_cost_usd": cost_breakdown.get("context_cache_cost_usd") if cost_breakdown else None,
            "model": model_name,
            "pricing_tier": cost_breakdown.get("pricing_tier", "standard") if cost_breakdown else "standard",
            "input_price_per_m": cost_breakdown.get("input_price_per_m") if cost_breakdown else None,
            "output_price_per_m": cost_breakdown.get("output_price_per_m") if cost_breakdown else None,
            "max_tokens_remaining": max_tokens_remaining,
            "compression_ratio": compression_ratio
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (these are already formatted)
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else (type(e).__name__ if type(e).__name__ else "Unknown error")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error counting tokens: {error_msg}")


@app.post("/tokenize", response_model=TokenStatsResponse)
async def tokenize(request: TokenizeRequest) -> TokenStatsResponse:
    """
    Tokenize endpoint that returns token usage statistics
    
    Args:
        request: TokenizeRequest containing model and prompt
        
    Returns:
        TokenStatsResponse with token statistics
    """
    try:
        # Validate model name
        if "gemini" not in request.model.lower() and "gpt" not in request.model.lower():
            # Default to Gemini for non-specified models
            model_name = "gemini-2.5-flash"
        elif "gemini" in request.model.lower():
            # Extract or map Gemini model name
            if "2.5" in request.model.lower() or "flash" in request.model.lower():
                model_name = "gemini-2.5-flash"
            else:
                model_name = "gemini-2.5-flash"  # Default
        else:
            # For GPT models, we'll use a basic estimation
            # This is a fallback - ideally you'd use OpenAI's tiktoken
            model_name = request.model
        
        # Get token statistics following the workflow:
        # 1. Choose model
        # 2. Get input tokens (prompt + context) and output tokens (response + thinking)
        # 3. Calculate cost: (input_tokens / 1M) × input_cost + (output_tokens / 1M) × output_cost + extra fees
        stats = count_tokens_with_gemini(
            prompt=request.prompt,
            model_name=model_name,
            generate=request.generate,
            context_cache_tokens=request.context_cache_tokens or 0,
            context_cache_storage_hours=request.context_cache_storage_hours or 0.0
        )
        
        return TokenStatsResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else (type(e).__name__ if type(e).__name__ else "Unknown error")
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in tokenize endpoint: {error_msg}")
        print(f"Traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {error_msg}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "TokenStats MCP Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "tokenize": "POST /tokenize"
        }
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
                        "name": "tokenstats",
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
                            "name": "tokenize",
                            "description": "Tokenize text and return token usage statistics with cost calculation using Gemini API pricing",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "model": {
                                        "type": "string",
                                        "description": "Model name (e.g., gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-pro). Defaults to gemini-2.5-flash if not specified."
                                    },
                                    "prompt": {
                                        "type": "string",
                                        "description": "Text to tokenize"
                                    },
                                    "generate": {
                                        "type": "boolean",
                                        "description": "If true, make actual API call to get real token counts and costs. If false, only count tokens and estimate costs.",
                                        "default": False
                                    }
                                },
                                "required": ["model", "prompt"]
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
            if tool_name == "tokenize":
                model = tool_args.get("model")
                prompt = tool_args.get("prompt")
                if not model or not prompt:
                    raise HTTPException(status_code=400, detail="model and prompt parameters are required")
                tokenize_request = TokenizeRequest(model=model, prompt=prompt)
                result = await tokenize(tokenize_request)
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


@app.post("/sse")
async def mcp_sse_endpoint_post(request: Request):
    """
    MCP protocol endpoint via Server-Sent Events (SSE) - POST method
    For MCP Inspector streamable HTTP connections
    """
    return await mcp_sse_endpoint(request)

@app.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    MCP protocol endpoint via Server-Sent Events (SSE)
    For MCP Inspector streamable HTTP connections
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Read the request body if present
            body = {}
            try:
                body_text = await request.body()
                if body_text:
                    body = json.loads(body_text)
            except:
                pass
            
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
                            "name": "tokenstats",
                            "version": "1.0.0"
                        }
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
            elif method == "tools/list":
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "tokenize",
                                "description": "Tokenize text and return token usage statistics with cost calculation using Gemini API pricing",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "model": {
                                            "type": "string",
                                            "description": "Model name (e.g., gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-pro). Defaults to gemini-2.5-flash if not specified."
                                        },
                                        "prompt": {
                                            "type": "string",
                                            "description": "Text to tokenize"
                                        },
                                        "generate": {
                                            "type": "boolean",
                                            "description": "If true, make actual API call to get real token counts and costs. If false, only count tokens and estimate costs.",
                                            "default": False
                                        }
                                    },
                                    "required": ["model", "prompt"]
                                }
                            }
                        ]
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
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
                if tool_name == "tokenize":
                    model = tool_args.get("model")
                    prompt = tool_args.get("prompt")
                    if not model or not prompt:
                        response = {
                            "jsonrpc": jsonrpc,
                            "id": request_id,
                            "error": {
                                "code": -32602,
                                "message": "model and prompt parameters are required"
                            }
                        }
                        yield f"data: {json.dumps(response)}\n\n"
                    else:
                        tokenize_request = TokenizeRequest(model=model, prompt=prompt)
                        result = await tokenize(tokenize_request)
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
                        yield f"data: {json.dumps(response)}\n\n"
                else:
                    response = {
                        "jsonrpc": jsonrpc,
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {tool_name}"
                        }
                    }
                    yield f"data: {json.dumps(response)}\n\n"
            else:
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            yield f"data: {json.dumps(error_response)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    try:
        print(f"🚀 Starting TokenStats MCP Server on http://0.0.0.0:{port}")
        print(f"   Press Ctrl+C to stop the server")
        print()
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n✅ Server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting server: {e}", file=sys.stderr)
        sys.exit(1)

