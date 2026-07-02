param(
    [string]$BaseUrl = "https://api.deepseek.com",
    [string]$Model = "deepseek-v4-flash"
)

$ErrorActionPreference = "Stop"

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "DEEPSEEK_API_KEY is not set. Real DeepSeek test skipped."
    exit 0
}

if ($env:USE_REAL_LLM -ne "1") {
    Write-Host "USE_REAL_LLM is not 1. Real DeepSeek test skipped."
    exit 0
}

$Endpoint = $BaseUrl.TrimEnd("/")
if ($Endpoint.EndsWith("/v1")) {
    $Endpoint = $Endpoint.Substring(0, $Endpoint.Length - 3)
}
if (-not $Endpoint.EndsWith("/chat/completions")) {
    $Endpoint = "$Endpoint/chat/completions"
}

$Payload = @{
    model = $Model
    messages = @(
        @{
            role = "user"
            content = "只回复 OK"
        }
    )
    max_tokens = 20
    temperature = 0.1
    stream = $false
} | ConvertTo-Json -Depth 5

$Headers = @{
    Authorization = "Bearer $env:DEEPSEEK_API_KEY"
    "Content-Type" = "application/json"
}

try {
    $Response = Invoke-WebRequest -Uri $Endpoint -Method POST -Headers $Headers -Body $Payload -TimeoutSec 20 -UseBasicParsing
    $Json = $Response.Content | ConvertFrom-Json
    $Text = [string]$Json.choices[0].message.content
    if ($Text.Length -gt 100) {
        $Text = $Text.Substring(0, 100)
    }
    Write-Host "statusCode=$($Response.StatusCode)"
    Write-Host "model=$Model"
    Write-Host "ok=true"
    Write-Host "contentPreview=$Text"
}
catch {
    $StatusCode = $null
    $Reason = "network error"
    if ($_.Exception.Response) {
        $StatusCode = [int]$_.Exception.Response.StatusCode
        switch ($StatusCode) {
            401 { $Reason = "API Key invalid or expired" }
            402 { $Reason = "balance or quota is insufficient" }
            404 { $Reason = "model name or URL is incorrect" }
            429 { $Reason = "rate limited" }
            default { $Reason = "HTTP $StatusCode" }
        }
    }
    elseif ($_.Exception.Message -match "timeout") {
        $Reason = "timeout"
    }

    Write-Host "statusCode=$StatusCode"
    Write-Host "model=$Model"
    Write-Host "ok=false"
    Write-Host "reason=$Reason"
    Write-Host "detail=$($_.Exception.Message)"
    exit 1
}
