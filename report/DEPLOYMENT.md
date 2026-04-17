# Deployment Information

Student Name: Huynh Van Nghia  
Student ID: 2A202600085  
Date: 2026-04-17

## Public URL
https://twoa202600085-huynhvannghia-day12.onrender.com

## Platform
Render

## Current Deployment State
- GET /health: HTTP 200, status=degraded
- GET /ready: HTTP 503, detail=Service is not initialized
- Cause: Redis is required but REDIS_URL is not set to the Internal Redis URL.

## Required Environment Variables
- OPENAI_API_KEY
- AGENT_API_KEY
- REDIS_URL
- REQUIRE_REDIS=true
- RATE_LIMIT_PER_MINUTE=10
- MONTHLY_BUDGET_USD=10.0
- ENVIRONMENT=production
- LOG_LEVEL=INFO

## Fix for /ready on Render
1. Create a Redis service on Render (Key Value).
2. Copy Internal Redis URL from that Redis service.
3. Set REDIS_URL of this web service to that Internal Redis URL.
4. Redeploy the service.
5. Re-check /health and /ready.

## Test Commands

### Health Check
```bash
curl -i https://twoa202600085-huynhvannghia-day12.onrender.com/health
```

### Ready Check
```bash
curl -i https://twoa202600085-huynhvannghia-day12.onrender.com/ready
```

### Authentication Required (expect 401)
```powershell
$body = @{ user_id='report-401'; question='hello' } | ConvertTo-Json -Compress
try {
  Invoke-RestMethod -Method Post `
    -Uri "https://twoa202600085-huynhvannghia-day12.onrender.com/ask" `
    -Headers @{ 'Content-Type'='application/json' } `
    -Body $body -ErrorAction Stop
  "UNEXPECTED: 200"
} catch {
  [int]$_.Exception.Response.StatusCode
}
```

### Authenticated Prompt (replace API key)
```bash
curl -X POST https://twoa202600085-huynhvannghia-day12.onrender.com/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"render-test","question":"Hello"}'
```

### Rate Limit Test (local validated)
```python
import json, urllib.request, urllib.error, time, collections
base = "http://localhost:8000/ask"
key = "YOUR_LOCAL_OR_RENDER_KEY"
u = "rate-report-" + str(int(time.time()))
c = collections.Counter()
for i in range(1, 41):
    data = json.dumps({"user_id": u, "question": f"spam {i}"}).encode()
    req = urllib.request.Request(
        base,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req) as r:
            c[r.status] += 1
    except urllib.error.HTTPError as e:
        c[e.code] += 1
print(dict(c))
# Example result: {200: 21, 429: 19}
```

## Evidence Snapshot (2026-04-17)
- Render /health: 200 with redis=false, redis_required=true
- Render /ready: 503 Service is not initialized
- Render /ask without X-API-Key: 401
- Local burst test: {200: 21, 429: 19}
- Local context recall: "Your previous message was: \"My name is Alice\""

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)

## Repository URL
https://github.com/NghiaHV2010/2A202600085-HuynhVanNghia-Day12
