"""
MCP Server: AgentInventory
Remote server for tracking agent metadata, usage, and performance metrics
"""

import json
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import statistics

# Google Cloud imports (optional - will fail gracefully if not configured)
try:
    from google.cloud import aiplatform
    from google.cloud import monitoring_v3
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    aiplatform = None
    monitoring_v3 = None

# Load environment variables
# Try to load from script directory first, then current directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback to default behavior

# Google Cloud configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "")  # Project number (different from project ID)
LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GCP_API_KEY = os.getenv("GCP_API_KEY", "")  # Optional API key for authentication
# Note: Reasoning Engine API requires location to be "global", not a specific region

# Initialize FastAPI app
app = FastAPI(title="AgentInventory MCP Server", version="1.0.0")

# Add CORS middleware for remote access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for agent metadata
# Format: {agent_id: {id, description, ...}}
agent_metadata: Dict[str, Dict[str, Any]] = {}

# Storage for execution records
# Format: {agent_id: [execution_record, ...]}
execution_records: Dict[str, List[Dict[str, Any]]] = {}


class AgentExecution(BaseModel):
    """Model for recording an agent execution"""
    agent_id: str
    execution_id: Optional[str] = None
    timestamp: Optional[str] = None
    success: bool = True
    runtime_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error_message: Optional[str] = None


class AgentMetadata(BaseModel):
    """Model for agent metadata"""
    id: str
    description: str
    avg_cost: Optional[float] = None
    avg_latency: Optional[float] = None


class ListAgentsResponse(BaseModel):
    """Response model for list_agents endpoint"""
    agents: List[Dict[str, Any]]


class AgentUsageResponse(BaseModel):
    """Response model for usage endpoint"""
    total_runs: int
    failures: int
    avg_input_tokens: float
    avg_output_tokens: float
    p50_latency_ms: float
    p95_latency_ms: float


def calculate_percentile(data: List[float], percentile: float) -> float:
    """
    Calculate percentile from a list of values
    
    Args:
        data: List of numeric values
        percentile: Percentile to calculate (0-100)
        
    Returns:
        float: Percentile value
    """
    if not data:
        return 0.0
    
    sorted_data = sorted(data)
    index = (percentile / 100.0) * (len(sorted_data) - 1)
    
    if index.is_integer():
        return sorted_data[int(index)]
    else:
        lower = sorted_data[int(index)]
        upper = sorted_data[int(index) + 1]
        return lower + (upper - lower) * (index - int(index))


def record_execution(execution: AgentExecution) -> None:
    """
    Record an agent execution in the inventory
    
    Args:
        execution: AgentExecution object with execution details
    """
    agent_id = execution.agent_id
    
    # Initialize agent if not exists
    if agent_id not in agent_metadata:
        agent_metadata[agent_id] = {
            "id": agent_id,
            "description": f"Agent {agent_id}",
        }
    
    if agent_id not in execution_records:
        execution_records[agent_id] = []
    
    # Create execution record
    execution_data = {
        "execution_id": execution.execution_id or f"{agent_id}_{datetime.now().timestamp()}",
        "timestamp": execution.timestamp or datetime.now().isoformat(),
        "success": execution.success,
        "runtime_ms": execution.runtime_ms,
        "input_tokens": execution.input_tokens,
        "output_tokens": execution.output_tokens,
        "total_tokens": execution.total_tokens,
        "cost_usd": execution.cost_usd,
        "error_message": execution.error_message,
    }
    
    # Add to records
    execution_records[agent_id].append(execution_data)
    
    # Update agent metadata with averages
    update_agent_averages(agent_id)


def update_agent_averages(agent_id: str) -> None:
    """
    Update agent metadata with average cost and latency
    
    Args:
        agent_id: The ID of the agent
    """
    records = execution_records.get(agent_id, [])
    if not records:
        return
    
    # Calculate average cost
    costs = [r.get("cost_usd") for r in records if r.get("cost_usd") is not None]
    avg_cost = sum(costs) / len(costs) if costs else None
    
    # Calculate average latency
    latencies = [r.get("runtime_ms") for r in records if r.get("runtime_ms") is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    
    # Update metadata
    if agent_id in agent_metadata:
        if avg_cost is not None:
            agent_metadata[agent_id]["avg_cost"] = round(avg_cost, 6)
        if avg_latency is not None:
            agent_metadata[agent_id]["avg_latency"] = round(avg_latency, 2)


@app.post("/record_execution")
async def record_agent_execution(execution: AgentExecution) -> Dict[str, Any]:
    """
    Record an agent execution in the inventory
    
    Args:
        execution: AgentExecution object with execution details
        
    Returns:
        dict: Confirmation of recorded execution
    """
    try:
        record_execution(execution)
        return {
            "status": "success",
            "message": f"Execution recorded for agent {execution.agent_id}",
            "execution_id": execution.execution_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording execution: {str(e)}")


@app.post("/register_agent")
async def register_agent(metadata: AgentMetadata) -> Dict[str, Any]:
    """
    Register or update agent metadata
    
    Args:
        metadata: AgentMetadata object with agent information
        
    Returns:
        dict: Confirmation of registration
    """
    try:
        agent_metadata[metadata.id] = {
            "id": metadata.id,
            "description": metadata.description,
            "avg_cost": metadata.avg_cost,
            "avg_latency": metadata.avg_latency,
        }
        
        # Update averages from execution records if available
        update_agent_averages(metadata.id)
        
        return {
            "status": "success",
            "message": f"Agent {metadata.id} registered/updated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering agent: {str(e)}")


@app.get("/local/agents", response_model=ListAgentsResponse)
async def list_local_agents() -> ListAgentsResponse:
    """
    List all local agents in the inventory with their metadata
    
    Returns:
        ListAgentsResponse: List of all local agents with metadata
    """
    try:
        agents_list = []
        
        for agent_id, metadata in agent_metadata.items():
            # Ensure averages are up to date
            update_agent_averages(agent_id)
            
            agent_info = {
                "id": metadata.get("id", agent_id),
                "description": metadata.get("description", f"Agent {agent_id}"),
                "avg_cost": metadata.get("avg_cost"),
                "avg_latency": metadata.get("avg_latency"),
            }
            agents_list.append(agent_info)
        
        # Sort by agent ID
        agents_list.sort(key=lambda x: x["id"])
        
        return ListAgentsResponse(agents=agents_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing local agents: {str(e)}")


@app.get("/list_agents", response_model=ListAgentsResponse)
async def list_agents() -> ListAgentsResponse:
    """
    [DEPRECATED] List all agents in the inventory with their metadata
    Use /local/agents instead.
    
    Returns:
        ListAgentsResponse: List of all agents with metadata
    """
    return await list_local_agents()


@app.get("/local/agents/{agent_id}/usage", response_model=AgentUsageResponse)
async def get_local_agent_usage(agent_id: str) -> AgentUsageResponse:
    """
    Get detailed usage statistics for a specific local agent
    
    Args:
        agent_id: The ID of the local agent
        
    Returns:
        AgentUsageResponse: Detailed usage statistics
    """
    return await get_agent_usage_internal(agent_id)


@app.get("/usage", response_model=AgentUsageResponse)
async def get_agent_usage(agent: str = Query(..., description="Agent ID to get usage for")) -> AgentUsageResponse:
    """
    [DEPRECATED] Get detailed usage statistics for a specific agent
    Use /local/agents/{agent_id}/usage instead.
    
    Args:
        agent: The ID of the agent (query parameter)
        
    Returns:
        AgentUsageResponse: Detailed usage statistics
    """
    return await get_agent_usage_internal(agent)


async def get_agent_usage_internal(agent_id: str) -> AgentUsageResponse:
    """
    Internal function to get detailed usage statistics for a specific local agent
    
    Args:
        agent_id: The ID of the agent
        
    Returns:
        AgentUsageResponse: Detailed usage statistics
    """
    try:
        
        if agent_id not in agent_metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found in inventory"
            )
        
        records = execution_records.get(agent_id, [])
        
        if not records:
            return AgentUsageResponse(
                total_runs=0,
                failures=0,
                avg_input_tokens=0.0,
                avg_output_tokens=0.0,
                p50_latency_ms=0.0,
                p95_latency_ms=0.0,
            )
        
        # Calculate statistics
        total_runs = len(records)
        failures = sum(1 for r in records if not r.get("success", False))
        
        # Average input tokens
        input_tokens_list = [r.get("input_tokens", 0) for r in records if r.get("input_tokens") is not None]
        avg_input_tokens = sum(input_tokens_list) / len(input_tokens_list) if input_tokens_list else 0.0
        
        # Average output tokens
        output_tokens_list = [r.get("output_tokens", 0) for r in records if r.get("output_tokens") is not None]
        avg_output_tokens = sum(output_tokens_list) / len(output_tokens_list) if output_tokens_list else 0.0
        
        # Latency percentiles
        latencies = [r.get("runtime_ms") for r in records if r.get("runtime_ms") is not None]
        p50_latency_ms = calculate_percentile(latencies, 50) if latencies else 0.0
        p95_latency_ms = calculate_percentile(latencies, 95) if latencies else 0.0
        
        return AgentUsageResponse(
            total_runs=total_runs,
            failures=failures,
            avg_input_tokens=round(avg_input_tokens, 2),
            avg_output_tokens=round(avg_output_tokens, 2),
            p50_latency_ms=round(p50_latency_ms, 2),
            p95_latency_ms=round(p95_latency_ms, 2),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting agent usage: {str(e)}")


@app.delete("/agent/{agent_id}")
async def delete_agent(agent_id: str) -> Dict[str, Any]:
    """
    Delete an agent and all its execution records from the inventory
    
    Args:
        agent_id: The ID of the agent to delete
        
    Returns:
        dict: Confirmation of deletion
    """
    try:
        if agent_id not in agent_metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found in inventory"
            )
        
        del agent_metadata[agent_id]
        if agent_id in execution_records:
            del execution_records[agent_id]
        
        return {
            "status": "success",
            "message": f"Agent {agent_id} and all its records deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting agent: {str(e)}")


# -----------------------------
# Google Cloud Monitoring APIs
# -----------------------------

@app.get("/deployed/agents")
async def list_deployed_agents():
    """
    List deployed agents from Google Cloud Vertex AI Reasoning Engine
    
    Returns:
        dict: List of deployed agents with their metadata from GCP
    """
    return await list_gcp_agents_internal()


@app.get("/mcp-reas-engine/agents")
async def list_gcp_agents():
    """
    [DEPRECATED] List deployed agents from Google Cloud Vertex AI Reasoning Engine
    Use /deployed/agents instead.
    
    Returns:
        dict: List of agents with their metadata from GCP
    """
    return await list_gcp_agents_internal()


async def list_gcp_agents_internal():
    """
    Internal function to list deployed agents from Google Cloud Vertex AI Reasoning Engine
    
    Returns:
        dict: List of agents with their metadata from GCP
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Google Cloud libraries not installed. Install with: pip install google-cloud-aiplatform google-cloud-monitoring"
        )
    
    if not PROJECT_ID:
        raise HTTPException(
            status_code=400,
            detail="GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable must be set"
        )
    
    try:
        # Use REST API directly (like MetricsAgent does) for better compatibility
        import requests
        from google.auth import default
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        
        # Define required OAuth scopes for Vertex AI APIs
        SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
        
        # Get project number if not set
        project_number = PROJECT_NUMBER
        if not project_number and PROJECT_ID:
            try:
                # Try to get project number from Resource Manager API
                if GCP_API_KEY:
                    # Use API key if available
                    resource_manager_url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}?key={GCP_API_KEY}"
                    proj_response = requests.get(resource_manager_url, timeout=10)
                else:
                    # Use OAuth with explicit scopes
                    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                    if credentials_file and os.path.exists(credentials_file):
                        credentials = service_account.Credentials.from_service_account_file(
                            credentials_file,
                            scopes=SCOPES
                        )
                        credentials.refresh(Request())
                    else:
                        credentials, _ = default(scopes=SCOPES)
                        credentials.refresh(Request())
                    
                    access_token = credentials.token
                    resource_manager_url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}"
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                    proj_response = requests.get(resource_manager_url, headers=headers, timeout=10)
                
                if proj_response.status_code == 200:
                    proj_data = proj_response.json()
                    project_number = str(proj_data.get("projectNumber", ""))
            except Exception:
                # If we can't get project number, we'll try with project ID (might not work)
                pass
        
        # Use project number if available, otherwise fall back to project ID
        project_identifier = project_number if project_number else PROJECT_ID
        
        if not project_identifier:
            raise HTTPException(
                status_code=400,
                detail="GCP_PROJECT_ID or GCP_PROJECT_NUMBER must be set"
            )
        
        # Prepare authentication - Reasoning Engine API requires OAuth2, not API keys
        headers = {
            "Content-Type": "application/json"
        }
        
        # Use OAuth2 token with explicit scopes (required by Reasoning Engine API)
        try:
            # Get credentials with explicit scopes for Vertex AI
            # If GOOGLE_APPLICATION_CREDENTIALS is set, use service account directly
            credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if credentials_file and os.path.exists(credentials_file):
                # Use service account credentials with explicit scopes
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_file,
                    scopes=SCOPES
                )
                credentials.refresh(Request())
            else:
                # Use default credentials (ADC) with explicit scopes
                credentials, _ = default(scopes=SCOPES)
                credentials.refresh(Request())
            
            access_token = credentials.token
            headers["Authorization"] = f"Bearer {access_token}"
        except Exception as auth_error:
            error_detail = str(auth_error)
            # Provide more helpful error messages
            if "invalid_scope" in error_detail.lower():
                error_detail = f"OAuth scope error: {error_detail}. Make sure your service account has the required permissions (roles/aiplatform.user or roles/aiplatform.admin)."
            raise HTTPException(
                status_code=401,
                detail=f"Authentication failed: {error_detail}. Configure GOOGLE_APPLICATION_CREDENTIALS with a valid service account JSON file."
            )
        
        result = []
        last_error = None  # Track the first error we encounter
        
        # Try both "global" and the configured region
        # ADK deploys to specific regions (e.g., us-central1), not global
        locations_to_try = [LOCATION, "global"]
        # Remove duplicates while preserving order
        locations_to_try = list(dict.fromkeys(locations_to_try))
        
        for location in locations_to_try:
            try:
                # Use REST API endpoint - Reasoning Engine API requires OAuth2
                # Note: API uses project NUMBER, not project ID
                # Always use googleapis.com domain (clients6.google.com doesn't support OAuth2 properly)
                base_url = f"https://{location}-aiplatform.googleapis.com/v1beta1"
                api_endpoint = f"{base_url}/projects/{project_identifier}/locations/{location}/reasoningEngines?pageSize=50"
                
                response = requests.get(api_endpoint, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if "reasoningEngines" in data and data["reasoningEngines"]:
                        for engine in data["reasoningEngines"]:
                            # Extract agent ID from full resource name
                            full_name = engine.get("name", "")
                            agent_id = full_name.split("/")[-1] if "/" in full_name else full_name
                            
                            result.append({
                                "id": full_name,  # Full resource name
                                "agent_id": agent_id,  # Short ID
                                "display_name": engine.get("displayName", agent_id),
                                "state": engine.get("state", "UNKNOWN"),
                                "location": location,
                                "create_time": engine.get("createTime", "").replace("T", " ").replace("Z", "")[:19] if engine.get("createTime") else None,
                                "update_time": engine.get("updateTime", "").replace("T", " ").replace("Z", "")[:19] if engine.get("updateTime") else None,
                            })
                        
                        # Found agents in this location
                        break
                elif response.status_code == 404:
                    # Location doesn't exist or no agents, try next location
                    continue
                else:
                    # Other error, capture for reporting
                    try:
                        error_data = response.json() if response.text else {}
                        error_msg = error_data.get("error", {}).get("message", response.text or f"HTTP {response.status_code}")
                    except:
                        error_msg = f"HTTP {response.status_code}: {response.text[:200] if response.text else 'No response body'}"
                    
                    # Store the first error we encounter for reporting
                    if last_error is None:
                        last_error = f"Location {location}: {error_msg}"
                    continue
                    
            except Exception as loc_error:
                # If one location fails, capture error and try the next one
                error_str = str(loc_error) or type(loc_error).__name__ or "Unknown error"
                if last_error is None:
                    last_error = f"Location {location}: {error_str}"
                continue
        
        # If we tried all locations and got no results, report the error if we encountered one
        if not result and last_error:
            raise HTTPException(
                status_code=500,
                detail=f"Error listing GCP agents: {last_error}"
            )
        
        return {"agents": result}
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = str(e) or type(e).__name__ or "Unknown error"
        raise HTTPException(status_code=500, detail=f"Error listing GCP agents: {error_msg}")


@app.get("/deployed/agents/{agent_id}/usage")
async def get_deployed_agent_usage(agent_id: str):
    """
    Get usage metrics from Google Cloud Monitoring for a specific deployed agent
    
    Args:
        agent_id: The ID of the deployed agent in GCP (can be full resource name or just the ID)
        
    Returns:
        dict: Usage metrics from Cloud Monitoring
    """
    return await get_gcp_agent_usage_internal(agent_id)


@app.get("/mcp-reas-engine/usage")
async def get_gcp_agent_usage(agent_id: str = Query(..., description="GCP Agent ID to get usage for")):
    """
    [DEPRECATED] Get usage metrics from Google Cloud Monitoring for a specific agent
    Use /deployed/agents/{agent_id}/usage instead.
    
    Args:
        agent_id: The ID of the agent in GCP (can be full resource name or just the ID)
        
    Returns:
        dict: Usage metrics from Cloud Monitoring
    """
    return await get_gcp_agent_usage_internal(agent_id)


async def get_gcp_agent_usage_internal(agent_id: str):
    """
    Get usage metrics from Google Cloud Monitoring for a specific agent
    
    Args:
        agent_id: The ID of the agent in GCP (can be full resource name or just the ID)
        
    Returns:
        dict: Usage metrics from Cloud Monitoring
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Google Cloud libraries not installed. Install with: pip install google-cloud-aiplatform google-cloud-monitoring"
        )
    
    if not PROJECT_ID:
        raise HTTPException(
            status_code=400,
            detail="GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable must be set"
        )
    
    try:
        # Extract just the agent ID from full resource name if provided
        # Format: projects/.../locations/.../reasoningEngines/AGENT_ID
        if "/reasoningEngines/" in agent_id:
            agent_id = agent_id.split("/reasoningEngines/")[-1]
        elif "/" in agent_id:
            # If it's just the last part after a slash
            agent_id = agent_id.split("/")[-1]
        
        # Initialize client with proper authentication scopes
        from google.auth import default
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        
        SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
        credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_file and os.path.exists(credentials_file):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=SCOPES
            )
            credentials.refresh(Request())
        else:
            credentials, _ = default(scopes=SCOPES)
            credentials.refresh(Request())
        
        client = monitoring_v3.MetricServiceClient(credentials=credentials)
        
        interval = monitoring_v3.TimeInterval(
            end_time=datetime.utcnow(),
            start_time=datetime.utcnow() - timedelta(hours=1),
        )
        
        # Use the standard Vertex AI Reasoning Engine metric
        metric_type = 'aiplatform.googleapis.com/reasoning_engine/request_count'
        
        # Build the filter - need to use reasoning_engine_id resource label
        # The agent_id from the API is the numeric ID (e.g., 328353754472513536)
        request_metric = (
            f'metric.type="{metric_type}" '
            f'resource.labels.reasoning_engine_id="{agent_id}"'
        )
        
        try:
            series = client.list_time_series(
                request={
                    "name": f"projects/{PROJECT_ID}",
                    "filter": request_metric,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )
            
            # Collect data points
            datapoints = []
            for ts in series:
                for pt in ts.points:
                    if hasattr(pt.value, 'int64_value'):
                        datapoints.append(pt.value.int64_value)
                    elif hasattr(pt.value, 'double_value'):
                        datapoints.append(int(pt.value.double_value))
            
            # If we got no data points, return info message
            if not datapoints:
                return {
                    "agent_id": agent_id,
                    "requests_last_hour": 0,
                    "info": "No usage data available for the last hour",
                    "note": f"Using metric: {metric_type}"
                }
            
            return {
                "agent_id": agent_id,
                "requests_last_hour": sum(datapoints) if datapoints else 0,
                "metric_type": metric_type,
            }
            
        except Exception as metric_error:
            error_str = str(metric_error)
            last_error = f"Metric {metric_type}: {error_str}"
            
            # Return usage data with error info
            return {
                "agent_id": agent_id,
                "requests_last_hour": 0,
                "warning": "No metrics found",
                "error": last_error,
                "error_type": type(metric_error).__name__,
                "note": f"Using metric: {metric_type}. Metrics may not be enabled or available yet for this agent."
            }
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Check if it's a permission error
        if "permission" in error_msg.lower() or "403" in error_msg or "forbidden" in error_msg.lower():
            error_detail = error_msg
            if hasattr(e, 'message'):
                error_detail = e.message
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied accessing Cloud Monitoring: {error_detail}. Ensure the service account has 'roles/monitoring.viewer' or 'roles/monitoring.metricReader' permissions."
            )
        
        # Extract more detailed error information
        if hasattr(e, 'code'):
            error_code = e.code
            error_msg = f"[{error_code}] {error_msg}"
        
        if hasattr(e, 'details'):
            error_details = str(e.details)
            if error_details:
                error_msg = f"{error_msg} - Details: {error_details}"
        
        # Extract gRPC error details if available
        if hasattr(e, 'grpc_status_code'):
            error_msg = f"gRPC {e.grpc_status_code}: {error_msg}"
        
        raise HTTPException(
            status_code=500,
            detail=f"Error getting GCP agent usage for '{agent_id}': {error_type} - {error_msg}"
        )


@app.get("/mcp-reas-engine/all")
async def get_gcp_all():
    """
    Get all GCP agents with their usage metrics merged
    
    Returns:
        dict: All agents from GCP with their usage metrics
    """
    if not GOOGLE_CLOUD_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Google Cloud libraries not installed. Install with: pip install google-cloud-aiplatform google-cloud-monitoring"
        )
    
    try:
        agents_response = await list_gcp_agents_internal()
        agents = agents_response["agents"]
        
        for a in agents:
            try:
                # Extract agent ID from the full resource name
                # Try agent_id field first, then id field
                agent_id = a.get("agent_id") or (a["id"].split("/")[-1] if "/" in a["id"] else a["id"])
                usage = await get_gcp_agent_usage_internal(agent_id=agent_id)
                a["usage"] = usage
            except HTTPException as http_err:
                # If usage fetch fails with HTTPException, include detailed error
                error_detail = http_err.detail if hasattr(http_err, 'detail') else str(http_err)
                a["usage"] = {
                    "requests_last_hour": 0,
                    "error": error_detail,
                    "error_type": "HTTPException"
                }
            except Exception as e:
                # If usage fetch fails, continue without usage data
                error_type = type(e).__name__
                error_str = str(e) or error_type or "Unknown error"
                
                # Try to extract more details
                if hasattr(e, 'message'):
                    error_str = f"{error_str} - {e.message}"
                if hasattr(e, 'details'):
                    error_str = f"{error_str} - Details: {e.details}"
                
                a["usage"] = {
                    "requests_last_hour": 0,
                    "error": error_str,
                    "error_type": error_type
                }
        
        return {"agents": agents}
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = str(e) or type(e).__name__ or "Unknown error"
        raise HTTPException(status_code=500, detail=f"Error getting all GCP agents: {error_msg}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "AgentInventory MCP Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "local_agents": "GET /local/agents",
            "local_usage": "GET /local/agents/{agent_id}/usage",
            "deployed_agents": "GET /deployed/agents",
            "deployed_usage": "GET /deployed/agents/{agent_id}/usage",
            "record_execution": "POST /record_execution",
            "register_agent": "POST /register_agent",
            "delete_agent": "DELETE /agent/{agent_id}",
            # Deprecated endpoints (kept for backward compatibility)
            "list_agents": "GET /list_agents [DEPRECATED - use /local/agents]",
            "usage": "GET /usage?agent={agent_id} [DEPRECATED - use /local/agents/{agent_id}/usage]",
            "mcp_reas_engine_agents": "GET /mcp-reas-engine/agents [DEPRECATED - use /deployed/agents]",
            "mcp_reas_engine_usage": "GET /mcp-reas-engine/usage?agent_id={agent_id} [DEPRECATED]",
            "mcp_reas_engine_all": "GET /mcp-reas-engine/all [DEPRECATED]",
        },
        "gcp_available": GOOGLE_CLOUD_AVAILABLE,
        "gcp_project_id": PROJECT_ID if PROJECT_ID else None,
        "gcp_project_number": PROJECT_NUMBER if PROJECT_NUMBER else None,
        "gcp_location": LOCATION,
        "gcp_oauth2_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        "gcp_configured": bool(PROJECT_ID),
        "agent_count": len(agent_metadata),
        "total_executions": sum(len(records) for records in execution_records.values()),
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
                        "name": "agent-inventory",
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
                            "name": "list_local_agents",
                            "description": "List all local agents in the inventory with their metadata",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        },
                        {
                            "name": "get_local_agent_usage",
                            "description": "Get detailed usage statistics for a specific local agent",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {
                                        "type": "string",
                                        "description": "The ID of the local agent"
                                    }
                                },
                                "required": ["agent_id"]
                            }
                        },
                        {
                            "name": "register_agent",
                            "description": "Register or update agent metadata",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "description": {"type": "string"},
                                    "avg_cost": {"type": "number"},
                                    "avg_latency": {"type": "number"}
                                },
                                "required": ["id", "description"]
                            }
                        },
                        {
                            "name": "record_execution",
                            "description": "Record an agent execution in the inventory",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "execution_id": {"type": "string"},
                                    "timestamp": {"type": "string"},
                                    "success": {"type": "boolean"},
                                    "runtime_ms": {"type": "number"},
                                    "input_tokens": {"type": "integer"},
                                    "output_tokens": {"type": "integer"},
                                    "total_tokens": {"type": "integer"},
                                    "cost_usd": {"type": "number"},
                                    "error_message": {"type": "string"}
                                },
                                "required": ["agent_id"]
                            }
                        },
                        {
                            "name": "delete_agent",
                            "description": "Delete an agent and all its execution records",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"}
                                },
                                "required": ["agent_id"]
                            }
                        },
                        {
                            "name": "list_deployed_agents",
                            "description": "List deployed agents from Google Cloud Vertex AI Reasoning Engine",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        },
                        {
                            "name": "get_deployed_agent_usage",
                            "description": "Get usage metrics from Google Cloud Monitoring for a specific deployed agent",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {
                                        "type": "string",
                                        "description": "The ID of the deployed agent in GCP (can be full resource name or just the ID)"
                                    }
                                },
                                "required": ["agent_id"]
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
            if tool_name == "list_local_agents":
                result = await list_local_agents()
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
            elif tool_name == "list_agents":  # Deprecated - backward compatibility
                result = await list_agents()
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
            elif tool_name == "get_local_agent_usage":
                agent_id = tool_args.get("agent_id")
                if not agent_id:
                    raise HTTPException(status_code=400, detail="agent_id parameter is required")
                result = await get_local_agent_usage(agent_id=agent_id)
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
            elif tool_name == "get_agent_usage":  # Deprecated - backward compatibility
                agent_id = tool_args.get("agent")
                if not agent_id:
                    raise HTTPException(status_code=400, detail="agent parameter is required")
                result = await get_agent_usage(agent=agent_id)
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
            elif tool_name == "register_agent":
                metadata = AgentMetadata(**tool_args)
                result = await register_agent(metadata)
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
            elif tool_name == "record_execution":
                execution = AgentExecution(**tool_args)
                result = await record_agent_execution(execution)
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
            elif tool_name == "delete_agent":
                agent_id = tool_args.get("agent_id")
                if not agent_id:
                    raise HTTPException(status_code=400, detail="agent_id parameter is required")
                result = await delete_agent(agent_id)
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
            elif tool_name == "list_deployed_agents":
                result = await list_deployed_agents()
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
            elif tool_name == "get_deployed_agent_usage":
                agent_id = tool_args.get("agent_id")
                if not agent_id:
                    raise HTTPException(status_code=400, detail="agent_id parameter is required")
                result = await get_deployed_agent_usage(agent_id=agent_id)
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
            elif tool_name == "list_gcp_agents":  # Deprecated - backward compatibility
                result = await list_gcp_agents()
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
            elif tool_name == "get_gcp_agent_usage":  # Deprecated - backward compatibility
                agent_id = tool_args.get("agent_id")
                if not agent_id:
                    raise HTTPException(status_code=400, detail="agent_id parameter is required")
                result = await get_gcp_agent_usage(agent_id=agent_id)
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
            elif tool_name == "get_gcp_all":  # Deprecated - backward compatibility
                result = await get_gcp_all()
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
    """MCP protocol endpoint via Server-Sent Events (SSE) - POST method"""
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
            
            # Handle different MCP methods - reuse existing endpoint logic
            if method == "initialize":
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "agent-inventory", "version": "1.0.0"}
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
            elif method == "tools/list":
                # Return tools list
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": {
                        "tools": [
                            {"name": "list_local_agents", "description": "List all local agents in the inventory with their metadata", "inputSchema": {"type": "object", "properties": {}}},
                            {"name": "get_local_agent_usage", "description": "Get detailed usage statistics for a specific local agent", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string", "description": "The ID of the local agent"}}, "required": ["agent_id"]}},
                            {"name": "register_agent", "description": "Register or update agent metadata", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "description": {"type": "string"}, "avg_cost": {"type": "number"}, "avg_latency": {"type": "number"}}, "required": ["id", "description"]}},
                            {"name": "record_execution", "description": "Record an agent execution in the inventory", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "execution_id": {"type": "string"}, "timestamp": {"type": "string"}, "success": {"type": "boolean"}, "runtime_ms": {"type": "number"}, "input_tokens": {"type": "integer"}, "output_tokens": {"type": "integer"}, "total_tokens": {"type": "integer"}, "cost_usd": {"type": "number"}, "error_message": {"type": "string"}}, "required": ["agent_id"]}},
                            {"name": "delete_agent", "description": "Delete an agent and all its execution records", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]}},
                            {"name": "list_deployed_agents", "description": "List deployed agents from Google Cloud Vertex AI Reasoning Engine", "inputSchema": {"type": "object", "properties": {}}},
                            {"name": "get_deployed_agent_usage", "description": "Get usage metrics from Google Cloud Monitoring for a specific deployed agent", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string", "description": "The ID of the deployed agent in GCP (can be full resource name or just the ID)"}}, "required": ["agent_id"]}}
                        ]
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
            elif method == "tools/call":
                # For tool calls, we need to use the existing endpoint logic
                # But since we can't read body twice, we'll need to handle it here
                # For now, return an error suggesting to use POST / instead
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Tool calls via SSE not yet fully implemented. Please use POST / endpoint for tool calls."
                    }
                }
                yield f"data: {json.dumps(response)}\n\n"
            else:
                response = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
                yield f"data: {json.dumps(response)}\n\n"
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in locals() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
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
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
