# PowerShell script to test the TokenStats MCP Server

# Configuration
$SERVER_URL = "http://localhost:8000"
$TEST_PROMPT = "Summarize: The quick brown fox jumps over the lazy dog. This is a test of the token counting functionality."

Write-Host "🧪 Testing TokenStats MCP Server" -ForegroundColor Green
Write-Host "Server URL: $SERVER_URL" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
try {
    $healthResponse = Invoke-RestMethod -Uri "$SERVER_URL/health" -Method GET
    Write-Host "✅ Health check passed: $($healthResponse.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ Health check failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Test 2: Tokenize Request
Write-Host "Test 2: Tokenize Request" -ForegroundColor Yellow
Write-Host "Prompt: $TEST_PROMPT" -ForegroundColor Gray
Write-Host ""

# Test 2a: Tokenize Request (Token counting only - no API call)
Write-Host "Test 2a: Tokenize Request (Token Count Only)" -ForegroundColor Yellow
$body = @{
    model = "gemini-2.5-flash"
    prompt = $TEST_PROMPT
    generate = $false
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$SERVER_URL/tokenize" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body

    Write-Host "✅ Tokenize request successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Token Statistics:" -ForegroundColor Cyan
    Write-Host "  Model: $($response.model)" -ForegroundColor White
    Write-Host "  Input Tokens: $($response.input_tokens)" -ForegroundColor White
    if ($response.estimated_output_tokens) {
        Write-Host "  Estimated Output Tokens: $($response.estimated_output_tokens)" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "Cost Breakdown:" -ForegroundColor Cyan
    Write-Host "  Input Cost: `$$($response.input_cost_usd) (Formula: $($response.input_tokens) / 1M × `$$($response.input_price_per_m))" -ForegroundColor White
    Write-Host "  Output Cost (estimated): `$$($response.output_cost_usd) (Formula: $($response.estimated_output_tokens) / 1M × `$$($response.output_price_per_m))" -ForegroundColor White
    if ($response.context_cache_cost_usd) {
        Write-Host "  Context Cache Cost: `$$($response.context_cache_cost_usd)" -ForegroundColor White
    }
    Write-Host "  Total Cost (estimated): `$$($response.estimated_cost_usd)" -ForegroundColor Green
    Write-Host "  Pricing Tier: $($response.pricing_tier)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Other Stats:" -ForegroundColor Cyan
    Write-Host "  Max Tokens Remaining: $($response.max_tokens_remaining)" -ForegroundColor White
    if ($response.compression_ratio) {
        Write-Host "  Compression Ratio: $($response.compression_ratio)" -ForegroundColor White
    }
    Write-Host ""
    
    # Pretty JSON output
    Write-Host "Full Response:" -ForegroundColor Cyan
    $response | ConvertTo-Json -Depth 10 | Write-Host
    
} catch {
    Write-Host "❌ Tokenize request failed: $_" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
    exit 1
}

Write-Host ""

# Test 2b: Tokenize Request with Actual API Call (Gets Real Costs)
Write-Host "Test 2b: Tokenize Request with Actual API Call (Real Costs)" -ForegroundColor Yellow
Write-Host "Prompt: $TEST_PROMPT" -ForegroundColor Gray
Write-Host ""

$bodyGenerate = @{
    model = "gemini-2.5-flash"
    prompt = $TEST_PROMPT
    generate = $true
} | ConvertTo-Json

try {
    $responseGenerate = Invoke-RestMethod -Uri "$SERVER_URL/tokenize" `
        -Method POST `
        -ContentType "application/json" `
        -Body $bodyGenerate

    Write-Host "✅ Tokenize with API call successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Token Statistics (Actual):" -ForegroundColor Cyan
    Write-Host "  Model: $($responseGenerate.model)" -ForegroundColor White
    Write-Host "  Input Tokens: $($responseGenerate.input_tokens)" -ForegroundColor White
    if ($responseGenerate.actual_output_tokens) {
        Write-Host "  Actual Output Tokens: $($responseGenerate.actual_output_tokens)" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "Cost Breakdown (Actual):" -ForegroundColor Cyan
    Write-Host "  Input Cost: `$$($responseGenerate.input_cost_usd) (Formula: $($responseGenerate.input_tokens) / 1M × `$$($responseGenerate.input_price_per_m))" -ForegroundColor White
    Write-Host "  Output Cost: `$$($responseGenerate.output_cost_usd) (Formula: $($responseGenerate.actual_output_tokens) / 1M × `$$($responseGenerate.output_price_per_m))" -ForegroundColor White
    if ($responseGenerate.context_cache_cost_usd) {
        Write-Host "  Context Cache Cost: `$$($responseGenerate.context_cache_cost_usd)" -ForegroundColor White
    }
    Write-Host "  Total Cost (Actual): `$$($responseGenerate.actual_cost_usd)" -ForegroundColor Green
    Write-Host "  Pricing Tier: $($responseGenerate.pricing_tier)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Other Stats:" -ForegroundColor Cyan
    Write-Host "  Max Tokens Remaining: $($responseGenerate.max_tokens_remaining)" -ForegroundColor White
    if ($responseGenerate.compression_ratio) {
        Write-Host "  Compression Ratio: $($responseGenerate.compression_ratio)" -ForegroundColor White
    }
    Write-Host ""
    
    # Pretty JSON output
    Write-Host "Full Response:" -ForegroundColor Cyan
    $responseGenerate | ConvertTo-Json -Depth 10 | Write-Host
    
} catch {
    Write-Host "⚠️  Tokenize with API call failed (may require API key or model access): $_" -ForegroundColor Yellow
    if ($_.ErrorDetails.Message) {
        Write-Host "Error details: $($_.ErrorDetails.Message)" -ForegroundColor Yellow
    }
    Write-Host "  This is expected if GOOGLE_API_KEY is not set or model access is limited" -ForegroundColor Gray
    Write-Host ""
}

Write-Host ""
Write-Host "✅ All tests completed!" -ForegroundColor Green

