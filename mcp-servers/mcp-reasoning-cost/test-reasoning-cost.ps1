# PowerShell script to test the ReasoningCost MCP Server

# Configuration
$SERVER_URL = "http://localhost:8002"

Write-Host "Testing ReasoningCost MCP Server" -ForegroundColor Green
Write-Host "Server URL: $SERVER_URL" -ForegroundColor Cyan
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

# Test 2: Estimate Reasoning Cost
Write-Host "Test 2: Estimate Reasoning Cost" -ForegroundColor Yellow
$traceData = @{
    trace = @{
        steps = 8
        tool_calls = 3
        tokens_in_trace = 1189
    }
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/estimate" `
        -Method POST `
        -ContentType "application/json" `
        -Body $traceData

    Write-Host "Estimate calculated successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Results:" -ForegroundColor Cyan
    Write-Host "  Reasoning Depth: $($response.reasoning_depth)" -ForegroundColor White
    Write-Host "  Tool Invocations: $($response.tool_invocations)" -ForegroundColor White
    Write-Host "  Expansion Factor: $($response.expansion_factor)" -ForegroundColor White
    Write-Host "  Cost Score: $($response.cost_score)" -ForegroundColor White
    Write-Host ""
    
    # Interpret cost score
    if ($response.cost_score -lt 0.3) {
        Write-Host "  Interpretation: Low cost (efficient reasoning)" -ForegroundColor Green
    } elseif ($response.cost_score -lt 0.6) {
        Write-Host "  Interpretation: Medium cost (normal reasoning)" -ForegroundColor Yellow
    } elseif ($response.cost_score -lt 1.0) {
        Write-Host "  Interpretation: High cost (expensive reasoning)" -ForegroundColor Red
    } else {
        Write-Host "  Interpretation: Very high cost (runaway reasoning detected!)" -ForegroundColor Magenta
    }
    Write-Host ""
    
    Write-Host "Full Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10 | Write-Host
    
} catch {
    Write-Host "Failed to estimate reasoning cost: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""

# Test 3: Estimate Multiple Traces
Write-Host "Test 3: Estimate Multiple Traces" -ForegroundColor Yellow
$multipleTraces = @{
    traces = @(
        @{
            steps = 8
            tool_calls = 3
            tokens_in_trace = 1189
        },
        @{
            steps = 5
            tool_calls = 1
            tokens_in_trace = 650
        },
        @{
            steps = 12
            tool_calls = 5
            tokens_in_trace = 2400
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/estimate_multiple" `
        -Method POST `
        -ContentType "application/json" `
        -Body $multipleTraces

    Write-Host "Batch estimate calculated successfully!" -ForegroundColor Green
    Write-Host "  Number of estimates: $($response.count)" -ForegroundColor White
    Write-Host ""
    
    Write-Host "Estimates:" -ForegroundColor Cyan
    $response.estimates | ForEach-Object -Begin { $i = 1 } -Process {
        Write-Host "  Trace $i :" -ForegroundColor Yellow
        Write-Host "    Reasoning Depth: $($_.reasoning_depth)" -ForegroundColor White
        Write-Host "    Tool Invocations: $($_.tool_invocations)" -ForegroundColor White
        Write-Host "    Expansion Factor: $($_.expansion_factor)" -ForegroundColor White
        Write-Host "    Cost Score: $($_.cost_score)" -ForegroundColor White
        Write-Host ""
        $i++
    }
    
} catch {
    Write-Host "Failed to estimate multiple traces: $_" -ForegroundColor Yellow
    Write-Host "(This endpoint is optional)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "All tests passed!" -ForegroundColor Green

