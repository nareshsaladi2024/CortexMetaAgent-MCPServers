# PowerShell script to test the AgentInventory MCP Server

# Load environment variables from .env file if it exists
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)\s*$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            if ($value -match '^["''](.*)["'']$') {
                $value = $matches[1]
            }
            
            # Resolve relative paths for GOOGLE_APPLICATION_CREDENTIALS
            if ($key -eq "GOOGLE_APPLICATION_CREDENTIALS" -and $value -and -not [System.IO.Path]::IsPathRooted($value)) {
                $resolvedPath = Join-Path $PSScriptRoot $value
                if (Test-Path $resolvedPath) {
                    $value = $resolvedPath
                    Write-Host "  Resolved relative path to: $value" -ForegroundColor Gray
                } else {
                    Write-Host "  Warning: GOOGLE_APPLICATION_CREDENTIALS path not found: $resolvedPath" -ForegroundColor Yellow
                }
            }
            
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "Environment variables loaded from .env" -ForegroundColor Gray
    Write-Host ""
}

# Configuration
$PORT = if ($env:PORT) { $env:PORT } else { "8001" }
$SERVER_URL = "http://localhost:$PORT"
$GCP_PROJECT_ID = $env:GCP_PROJECT_ID
$GCP_PROJECT_NUMBER = $env:GCP_PROJECT_NUMBER
$GCP_LOCATION = if ($env:GCP_LOCATION) { $env:GCP_LOCATION } else { "us-central1" }
$GCP_API_KEY = $env:GCP_API_KEY

Write-Host "Testing AgentInventory MCP Server" -ForegroundColor Green
Write-Host "Server URL: $SERVER_URL" -ForegroundColor Cyan
Write-Host "Port: $PORT" -ForegroundColor Cyan
if ($GCP_PROJECT_ID) {
    Write-Host "GCP Project ID: $GCP_PROJECT_ID" -ForegroundColor Cyan
    if ($GCP_PROJECT_NUMBER) {
        Write-Host "GCP Project Number: $GCP_PROJECT_NUMBER" -ForegroundColor Cyan
    } else {
        Write-Host "GCP Project Number: Not set (will try to fetch automatically)" -ForegroundColor Yellow
    }
    Write-Host "GCP Location: $GCP_LOCATION" -ForegroundColor Cyan
    
    # Check OAuth2 authentication (required for Reasoning Engine API)
    if ($env:GOOGLE_APPLICATION_CREDENTIALS) {
        if (Test-Path $env:GOOGLE_APPLICATION_CREDENTIALS) {
            Write-Host "OAuth2: Service Account configured" -ForegroundColor Green
            Write-Host "  Service Account: $env:GOOGLE_APPLICATION_CREDENTIALS" -ForegroundColor Gray
        } else {
            Write-Host "OAuth2: Service Account file not found!" -ForegroundColor Red
            Write-Host "  Path: $env:GOOGLE_APPLICATION_CREDENTIALS" -ForegroundColor Gray
        }
    } else {
        Write-Host "OAuth2: Not configured (will use Application Default Credentials)" -ForegroundColor Yellow
        Write-Host "  Set GOOGLE_APPLICATION_CREDENTIALS or run 'gcloud auth application-default login'" -ForegroundColor Gray
    }
    
    if ($GCP_API_KEY) {
        Write-Host "GCP API Key: Configured (only used for Resource Manager API)" -ForegroundColor Gray
    }
} else {
    Write-Host "GCP Project ID: Not configured (MCP Reasoning Engine endpoints will not work)" -ForegroundColor Yellow
}
Write-Host ""

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
try {
    $healthResponse = Invoke-RestMethod -Uri "$SERVER_URL/health" -Method GET
    Write-Host "Health check passed: $($healthResponse.status)" -ForegroundColor Green
} catch {
    Write-Host "Health check failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 2: Record Execution
Write-Host "Test 2: Record Agent Execution" -ForegroundColor Yellow
$executionData = @{
    agent_id = "test-summarizer-agent"
    execution_id = "test_exec_001"
    success = $true
    runtime_ms = 1250.5
    input_tokens = 150
    output_tokens = 75
    total_tokens = 225
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/record_execution" `
        -Method POST `
        -ContentType "application/json" `
        -Body $executionData

    Write-Host "Execution recorded successfully!" -ForegroundColor Green
    Write-Host "  Status: $($response.status)" -ForegroundColor White
    Write-Host "  Message: $($response.message)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to record execution: $_" -ForegroundColor Red
    exit 1
}

# Test 3: List Local Agents
Write-Host "Test 3: List Local Agents" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/local/agents" -Method GET
    
    Write-Host "Local agents listed successfully!" -ForegroundColor Green
    Write-Host "  Total agents: $($response.agents.Count)" -ForegroundColor White
    Write-Host ""
    
    if ($response.agents.Count -gt 0) {
        Write-Host "Agents:" -ForegroundColor Cyan
        $response.agents | ForEach-Object {
            Write-Host "  - ID: $($_.id)" -ForegroundColor White
            Write-Host "    Description: $($_.description)" -ForegroundColor Gray
            Write-Host "    Avg Cost: `$$($_.avg_cost)" -ForegroundColor Gray
            Write-Host "    Avg Latency: $($_.avg_latency) ms" -ForegroundColor Gray
            Write-Host ""
        }
    }
} catch {
    Write-Host "Failed to list agents: $_" -ForegroundColor Red
    exit 1
}

# Test 4: Register Agents
Write-Host "Test 4: Register Agents" -ForegroundColor Yellow
$retrieverMetadata = @{
    id = "retriever"
    description = "Document retrieval via vector search"
} | ConvertTo-Json

$summarizerMetadata = @{
    id = "summarizer"
    description = "Long document compressor"
} | ConvertTo-Json

try {
    $response1 = Invoke-RestMethod -Uri "$SERVER_URL/register_agent" `
        -Method POST `
        -ContentType "application/json" `
        -Body $retrieverMetadata
    
    $response2 = Invoke-RestMethod -Uri "$SERVER_URL/register_agent" `
        -Method POST `
        -ContentType "application/json" `
        -Body $summarizerMetadata
    
    Write-Host "Agents registered successfully!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Failed to register agents: $_" -ForegroundColor Yellow
    Write-Host "(Agents may already be registered)" -ForegroundColor Gray
    Write-Host ""
}

# Test 5: Record More Executions for Statistics
Write-Host "Test 5: Record Additional Executions" -ForegroundColor Yellow
for ($i = 1; $i -le 5; $i++) {
    $execData = @{
        agent_id = "retriever"
        success = $true
        runtime_ms = (300 + (Get-Random -Minimum 0 -Maximum 200))
        input_tokens = 200 + (Get-Random -Minimum 0 -Maximum 50)
        output_tokens = 50 + (Get-Random -Minimum 0 -Maximum 20)
        cost_usd = 0.0005 + (Get-Random -Minimum 0 -Maximum 0.0005)
    } | ConvertTo-Json
    
    try {
        Invoke-RestMethod -Uri "$SERVER_URL/record_execution" `
            -Method POST `
            -ContentType "application/json" `
            -Body $execData | Out-Null
    } catch {
        # Ignore errors
    }
}
Write-Host "Additional executions recorded" -ForegroundColor Green
Write-Host ""

# Test 6: Get Local Agent Usage
Write-Host "Test 6: Get Local Agent Usage" -ForegroundColor Yellow
$agentId = "retriever"
try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/local/agents/$agentId/usage" -Method GET
    
    Write-Host "Agent usage retrieved successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage Statistics:" -ForegroundColor Cyan
    Write-Host "  Total Runs: $($response.total_runs)" -ForegroundColor White
    Write-Host "  Failures: $($response.failures)" -ForegroundColor White
    Write-Host "  Avg Input Tokens: $($response.avg_input_tokens)" -ForegroundColor White
    Write-Host "  Avg Output Tokens: $($response.avg_output_tokens)" -ForegroundColor White
    Write-Host "  P50 Latency: $($response.p50_latency_ms) ms" -ForegroundColor White
    Write-Host "  P95 Latency: $($response.p95_latency_ms) ms" -ForegroundColor White
    Write-Host ""
    
    Write-Host "Full Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10 | Write-Host
    
} catch {
    Write-Host "Failed to get agent usage: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""

# Test 7: MCP Protocol - Initialize
Write-Host "Test 7: MCP Protocol - Initialize" -ForegroundColor Yellow
$mcpInitRequest = @{
    jsonrpc = "2.0"
    id = 1
    method = "initialize"
    params = @{}
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpInitRequest
    
    Write-Host "MCP Initialize successful!" -ForegroundColor Green
    Write-Host "  Protocol Version: $($response.result.protocolVersion)" -ForegroundColor White
    Write-Host "  Server Name: $($response.result.serverInfo.name)" -ForegroundColor White
    Write-Host "  Server Version: $($response.result.serverInfo.version)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to initialize MCP: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 8: MCP Protocol - List Tools
Write-Host "Test 8: MCP Protocol - List Tools" -ForegroundColor Yellow
$mcpListToolsRequest = @{
    jsonrpc = "2.0"
    id = 2
    method = "tools/list"
    params = @{}
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpListToolsRequest
    
    Write-Host "MCP Tools listed successfully!" -ForegroundColor Green
    Write-Host "  Total tools: $($response.result.tools.Count)" -ForegroundColor White
    Write-Host ""
    Write-Host "Available Tools:" -ForegroundColor Cyan
    $response.result.tools | ForEach-Object {
        Write-Host "  - $($_.name): $($_.description)" -ForegroundColor White
    }
    Write-Host ""
} catch {
    Write-Host "Failed to list MCP tools: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 9: MCP Protocol - Call Tool: list_local_agents
Write-Host "Test 9: MCP Protocol - Call Tool: list_local_agents" -ForegroundColor Yellow
$mcpListAgentsRequest = @{
    jsonrpc = "2.0"
    id = 3
    method = "tools/call"
    params = @{
        name = "list_local_agents"
        arguments = @{}
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpListAgentsRequest
    
    Write-Host "MCP list_local_agents tool called successfully!" -ForegroundColor Green
    $resultText = $response.result.content[0].text
    $resultObj = $resultText | ConvertFrom-Json
    Write-Host "  Agents found: $($resultObj.agents.Count)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to call MCP list_local_agents tool: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 10: MCP Protocol - Call Tool: get_local_agent_usage
Write-Host "Test 10: MCP Protocol - Call Tool: get_local_agent_usage" -ForegroundColor Yellow
$mcpUsageRequest = @{
    jsonrpc = "2.0"
    id = 4
    method = "tools/call"
    params = @{
        name = "get_local_agent_usage"
        arguments = @{
            agent_id = "retriever"
        }
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpUsageRequest
    
    Write-Host "MCP get_local_agent_usage tool called successfully!" -ForegroundColor Green
    $resultText = $response.result.content[0].text
    $resultObj = $resultText | ConvertFrom-Json
    Write-Host "  Total Runs: $($resultObj.total_runs)" -ForegroundColor White
    Write-Host "  Failures: $($resultObj.failures)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to call MCP get_local_agent_usage tool: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 11: MCP Protocol - Call Tool: register_agent
Write-Host "Test 11: MCP Protocol - Call Tool: register_agent" -ForegroundColor Yellow
$mcpRegisterRequest = @{
    jsonrpc = "2.0"
    id = 5
    method = "tools/call"
    params = @{
        name = "register_agent"
        arguments = @{
            id = "mcp-test-agent"
            description = "Test agent registered via MCP protocol"
        }
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpRegisterRequest
    
    Write-Host "MCP register_agent tool called successfully!" -ForegroundColor Green
    $resultText = $response.result.content[0].text
    $resultObj = $resultText | ConvertFrom-Json
    Write-Host "  Status: $($resultObj.status)" -ForegroundColor White
    Write-Host "  Message: $($resultObj.message)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to call MCP register_agent tool: $_" -ForegroundColor Yellow
    Write-Host "(Agent may already be registered)" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""

# Test 12: MCP Protocol - Call Tool: record_execution
Write-Host "Test 12: MCP Protocol - Call Tool: record_execution" -ForegroundColor Yellow
$mcpRecordRequest = @{
    jsonrpc = "2.0"
    id = 6
    method = "tools/call"
    params = @{
        name = "record_execution"
        arguments = @{
            agent_id = "mcp-test-agent"
            success = $true
            runtime_ms = 500.0
            input_tokens = 100
            output_tokens = 50
            total_tokens = 150
        }
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
        -Method POST `
        -ContentType "application/json" `
        -Body $mcpRecordRequest
    
    Write-Host "MCP record_execution tool called successfully!" -ForegroundColor Green
    $resultText = $response.result.content[0].text
    $resultObj = $resultText | ConvertFrom-Json
    Write-Host "  Status: $($resultObj.status)" -ForegroundColor White
    Write-Host "  Message: $($resultObj.message)" -ForegroundColor White
    Write-Host ""
} catch {
    Write-Host "Failed to call MCP record_execution tool: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 12: MCP Protocol - Call Tool: list_deployed_agents (Optional - requires GCP setup)
Write-Host "Test 12: MCP Protocol - Call Tool: list_deployed_agents (Optional)" -ForegroundColor Yellow
if ($GCP_PROJECT_ID) {
    $mcpListDeployedRequest = @{
        jsonrpc = "2.0"
        id = 6
        method = "tools/call"
        params = @{
            name = "list_deployed_agents"
            arguments = @{}
        }
    } | ConvertTo-Json -Depth 10

    try {
        $response = Invoke-RestMethod -Uri "$SERVER_URL/" `
            -Method POST `
            -ContentType "application/json" `
            -Body $mcpListDeployedRequest
        
        Write-Host "MCP list_deployed_agents tool called successfully!" -ForegroundColor Green
        $resultText = $response.result.content[0].text
        $resultObj = $resultText | ConvertFrom-Json
        Write-Host "  Deployed agents found: $($resultObj.agents.Count)" -ForegroundColor White
        Write-Host ""
    } catch {
        Write-Host "Failed to call MCP list_deployed_agents tool: $_" -ForegroundColor Red
        if ($_.ErrorDetails.Message) {
            Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  Test skipped - GCP_PROJECT_ID not configured" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""

# Test 13: List Deployed Agents (Optional - requires GCP setup)
Write-Host "Test 13: List Deployed Agents (Optional)" -ForegroundColor Yellow
if ($GCP_PROJECT_ID) {
    Write-Host "  Using GCP Project ID: $GCP_PROJECT_ID" -ForegroundColor Gray
    if ($GCP_PROJECT_NUMBER) {
        Write-Host "  Using GCP Project Number: $GCP_PROJECT_NUMBER" -ForegroundColor Gray
    }
    Write-Host "  Using GCP Location: $GCP_LOCATION" -ForegroundColor Gray
    if ($env:GOOGLE_APPLICATION_CREDENTIALS) {
        Write-Host "  Using Service Account: $env:GOOGLE_APPLICATION_CREDENTIALS" -ForegroundColor Green
    } else {
        Write-Host "  Using OAuth2 authentication (required for Reasoning Engine API)" -ForegroundColor Yellow
        Write-Host "  Note: Reasoning Engine API requires OAuth2, not API keys" -ForegroundColor Gray
        Write-Host "  Set GOOGLE_APPLICATION_CREDENTIALS or run 'gcloud auth application-default login'" -ForegroundColor Gray
    }
} else {
    Write-Host "  GCP_PROJECT_ID not set in .env file - skipping test" -ForegroundColor Yellow
    Write-Host "  Set GCP_PROJECT_ID in .env to enable this test" -ForegroundColor Gray
}

if ($GCP_PROJECT_ID) {
    try {
        $response = Invoke-RestMethod -Uri "$SERVER_URL/deployed/agents" -Method GET
        
        Write-Host "Deployed agents listed successfully!" -ForegroundColor Green
        Write-Host "  Total agents: $($response.agents.Count)" -ForegroundColor White
        if ($response.agents.Count -gt 0) {
            Write-Host ""
            Write-Host "GCP Agents:" -ForegroundColor Cyan
            $response.agents | ForEach-Object {
                Write-Host "  - ID: $($_.id)" -ForegroundColor White
                Write-Host "    Display Name: $($_.display_name)" -ForegroundColor Gray
                Write-Host "    State: $($_.state)" -ForegroundColor Gray
                Write-Host ""
            }
        } else {
            Write-Host "  No deployed agents found in GCP project" -ForegroundColor Gray
        }
    } catch {
        Write-Host "Deployed agents endpoint not available" -ForegroundColor Yellow
        
        # Try to get detailed error message from response
        $errorDetail = ""
        try {
            if ($_.Exception.Response) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $reader.BaseStream.Position = 0
                $reader.DiscardBufferedData()
                $responseBody = $reader.ReadToEnd()
                try {
                    $errorObj = $responseBody | ConvertFrom-Json
                    if ($errorObj.detail) {
                        $errorDetail = $errorObj.detail
                    } elseif ($errorObj.message) {
                        $errorDetail = $errorObj.message
                    } elseif ($errorObj.error) {
                        $errorDetail = $errorObj.error
                    }
                } catch {
                    $errorDetail = $responseBody
                }
            }
        } catch {
            # If we can't read the response, use the exception message
            $errorDetail = $_.Exception.Message
        }
        
        if ($_.Exception.Response.StatusCode -eq 503) {
            Write-Host "  Google Cloud libraries not installed" -ForegroundColor Gray
            Write-Host "  Install with: pip install google-cloud-aiplatform google-cloud-monitoring" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            }
        } elseif ($_.Exception.Response.StatusCode -eq 400) {
            Write-Host "  GCP_PROJECT_ID not properly configured" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            }
        } elseif ($_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Response.StatusCode -eq 403) {
            Write-Host "  Google Cloud authentication failed" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            } else {
                Write-Host "  Ensure you have valid GCP credentials configured" -ForegroundColor Gray
                Write-Host "  Check GOOGLE_APPLICATION_CREDENTIALS environment variable" -ForegroundColor Gray
            }
        } else {
            Write-Host "  Error: $_" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            } elseif ($_.ErrorDetails.Message) {
                Write-Host "  Details: $($_.ErrorDetails.Message)" -ForegroundColor Gray
            }
        }
        Write-Host ""
    }
} else {
    Write-Host "  Test skipped - GCP_PROJECT_ID not configured" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""

# Test 14: Get Deployed Agent Usage (Optional - requires GCP setup)
Write-Host "Test 14: Get Deployed Agent Usage (Optional)" -ForegroundColor Yellow
if ($GCP_PROJECT_ID) {
    Write-Host "  Using GCP Project ID: $GCP_PROJECT_ID" -ForegroundColor Gray
    Write-Host "  Note: This test requires Google Cloud credentials to be configured" -ForegroundColor Gray
    
    # First get the list of deployed agents
    try {
        $agentsResponse = Invoke-RestMethod -Uri "$SERVER_URL/deployed/agents" -Method GET
        
        if ($agentsResponse.agents.Count -gt 0) {
            # Get usage for the first deployed agent
            $firstAgent = $agentsResponse.agents[0]
            $agentId = $firstAgent.agent_id
            if (-not $agentId) {
                # Extract agent ID from full resource name
                $agentId = $firstAgent.id.Split("/")[-1]
            }
            
            Write-Host "  Testing usage for agent: $agentId" -ForegroundColor Gray
            
            try {
                $usageResponse = Invoke-RestMethod -Uri "$SERVER_URL/deployed/agents/$agentId/usage" -Method GET
                
                Write-Host "Deployed agent usage retrieved successfully!" -ForegroundColor Green
                Write-Host "  Agent: $($firstAgent.display_name) ($agentId)" -ForegroundColor White
                if ($usageResponse.error) {
                    Write-Host "    Usage: Error" -ForegroundColor Red
                    Write-Host "      Error Type: $($usageResponse.error_type)" -ForegroundColor Yellow
                    Write-Host "      Error Details: $($usageResponse.error)" -ForegroundColor Yellow
                    if ($usageResponse.warning) {
                        Write-Host "      Warning: $($usageResponse.warning)" -ForegroundColor Yellow
                    }
                    if ($usageResponse.note) {
                        Write-Host "      Note: $($usageResponse.note)" -ForegroundColor Gray
                    }
                } elseif ($usageResponse.warning) {
                    Write-Host "    Usage: $($usageResponse.requests_last_hour) requests in last hour" -ForegroundColor Gray
                    Write-Host "      Warning: $($usageResponse.warning)" -ForegroundColor Yellow
                    if ($usageResponse.note) {
                        Write-Host "      Note: $($usageResponse.note)" -ForegroundColor Gray
                    }
                } elseif ($usageResponse.info) {
                    Write-Host "    Usage: $($usageResponse.requests_last_hour) requests in last hour" -ForegroundColor Gray
                    Write-Host "      Info: $($usageResponse.info)" -ForegroundColor Cyan
                } else {
                    Write-Host "    Usage: $($usageResponse.requests_last_hour) requests in last hour" -ForegroundColor Gray
                }
            } catch {
                Write-Host "Failed to get deployed agent usage: $_" -ForegroundColor Red
                if ($_.ErrorDetails.Message) {
                    Write-Host "  Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  No deployed agents found to test usage" -ForegroundColor Gray
        }
        Write-Host ""
    } catch {
        Write-Host "Deployed agents endpoint not available" -ForegroundColor Yellow
        
        # Try to get detailed error message from response
        $errorDetail = ""
        try {
            if ($_.Exception.Response) {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $reader.BaseStream.Position = 0
                $reader.DiscardBufferedData()
                $responseBody = $reader.ReadToEnd()
                try {
                    $errorObj = $responseBody | ConvertFrom-Json
                    if ($errorObj.detail) {
                        $errorDetail = $errorObj.detail
                    } elseif ($errorObj.message) {
                        $errorDetail = $errorObj.message
                    } elseif ($errorObj.error) {
                        $errorDetail = $errorObj.error
                    }
                } catch {
                    $errorDetail = $responseBody
                }
            }
        } catch {
            # If we can't read the response, use the exception message
            $errorDetail = $_.Exception.Message
        }
        
        if ($_.Exception.Response.StatusCode -eq 503) {
            Write-Host "  Google Cloud libraries not installed" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            }
        } elseif ($_.Exception.Response.StatusCode -eq 400) {
            Write-Host "  GCP_PROJECT_ID not properly configured" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            }
        } elseif ($_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Response.StatusCode -eq 403) {
            Write-Host "  Google Cloud authentication failed" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            } else {
                Write-Host "  Check GOOGLE_APPLICATION_CREDENTIALS environment variable" -ForegroundColor Gray
            }
        } else {
            Write-Host "  Error: $_" -ForegroundColor Gray
            if ($errorDetail) {
                Write-Host "  Details: $errorDetail" -ForegroundColor Gray
            }
        }
        Write-Host ""
    }
} else {
    Write-Host "  GCP_PROJECT_ID not set in .env file - skipping test" -ForegroundColor Yellow
    Write-Host "  Set GCP_PROJECT_ID in .env to enable this test" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""
Write-Host "All tests completed!" -ForegroundColor Green
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  - REST API endpoints: Tested" -ForegroundColor White
Write-Host "  - Local agents endpoints: Tested" -ForegroundColor White
Write-Host "  - Deployed agents endpoints: $(if ($GCP_PROJECT_ID) { 'Tested (GCP configured)' } else { 'Skipped (GCP not configured)' })" -ForegroundColor $(if ($GCP_PROJECT_ID) { 'White' } else { 'Yellow' })
Write-Host "  - MCP Protocol endpoints: Tested" -ForegroundColor White
if ($GCP_PROJECT_ID) {
    Write-Host "    Add GCP_PROJECT_ID to .env file to enable deployed agents tests" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  - Server URL: $SERVER_URL" -ForegroundColor White
Write-Host "  - Port: $PORT" -ForegroundColor White
if ($GCP_PROJECT_ID) {
    Write-Host "  - GCP Project: $GCP_PROJECT_ID" -ForegroundColor White
    Write-Host "  - GCP Location: $GCP_LOCATION" -ForegroundColor White
} else {
    Write-Host "  - GCP Project: Not configured" -ForegroundColor Yellow
}
Write-Host ""

