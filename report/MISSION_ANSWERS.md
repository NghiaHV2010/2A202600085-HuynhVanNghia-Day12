# Day 12 Lab - Mission Answers

Student Name: Huynh Van Nghia  
Student ID: 2A202600085  
Date: 2026-04-17

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Secrets can be hardcoded or loaded unsafely in localhost-style apps.
2. Missing readiness checks makes cloud orchestration unreliable.
3. In-memory state breaks when scaling to multiple instances.
4. No auth/rate/budget protection exposes API abuse risk.
5. Weak shutdown handling can drop in-flight requests during deploy.

### Exercise 1.2: Basic version run result
- Local basic app runs and is useful for concept learning.
- It is not enough for production because reliability and security controls are incomplete.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config | Minimal/default | Env-driven settings | One codebase for many environments |
| Secrets | Easy to leak | Managed by env vars/platform secrets | Security and compliance |
| Health | Often only liveness | Liveness + readiness | Safe rollout and restart |
| Logging | Plain text/print | Structured logs | Better monitoring and debugging |
| State | In-process memory | Redis-backed stateless design | Horizontal scaling support |
| Shutdown | Abrupt stop | Graceful shutdown hooks | Fewer failed requests |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: python:3.11-slim (production multi-stage).
2. Working directory: /app.
3. Why copy requirements first: improves cache reuse for dependency layer.
4. Why multi-stage: smaller runtime image and reduced attack surface.

### Exercise 2.2: Build and run notes
- Local run command: docker compose up -d --build
- Production Dockerfile uses non-root user and HEALTHCHECK.

### Exercise 2.3: Image size comparison
- Develop: ~800 MB (course baseline; local re-build blocked by Docker Hub unauthenticated pull rate limit 429 at report time).
- Production: 166 MB (measured from local image 06-lab-complete-agent:latest).
- Difference (baseline estimate): ~79.25% smaller.

## Part 3: Cloud Deployment

### Exercise 3.1: Deployed service
- Platform used: Render
- URL: https://twoa202600085-huynhvannghia-day12.onrender.com
- Status at report time:
  - GET /health -> 200, status=degraded
  - GET /ready -> 503, detail=Service is not initialized

### Exercise 3.2: Deployment notes
- Root cause of /ready failure: Redis required but REDIS_URL points to wrong value (must be Render Internal Redis URL, not HTTP app URL).
- Required fix on Render:
  1. Create Redis service (Key Value).
  2. Set REDIS_URL to Internal Redis URL.
  3. Keep REQUIRE_REDIS=true.
  4. Redeploy.

## Part 4: API Security

### Exercise 4.1-4.3: Test results

#### Render tests
- Health:
  - HTTP 200
  - Body includes redis=false and redis_required=true
- Readiness:
  - HTTP 503
  - detail: Service is not initialized
- Missing API key on /ask (JSON body serialized correctly):
  - HTTP 401 (PASS)

#### Local tests (06-lab-complete)
- Missing API key on /ask: HTTP 401 (PASS)
- Valid API key on /ask: HTTP 200 (PASS)
- Readiness when Redis stopped: HTTP 503 (PASS)
- Readiness after Redis restart: HTTP 200 (PASS)
- Rate-limit burst test (40 requests): {200: 21, 429: 19} (PASS)

### Exercise 4.4: Cost guard implementation
- Implemented in app/cost_guard.py.
- Enforces monthly budget via MONTHLY_BUDGET_USD.
- Usage tracked by month key; blocks requests when budget is exceeded.
- Monthly spend is exposed via metrics endpoint.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health and readiness
- /health: returns service and dependency status.
- /ready: blocks traffic when startup conditions are not satisfied.

### Exercise 5.2: Graceful shutdown
- Application uses lifespan and signal handling strategy to mark not-ready and shutdown cleanly.

### Exercise 5.3: Stateless design
- Conversation history is stored by user_id in Redis when available.
- Fallback memory store exists for local resilience, but production requires Redis.

### Exercise 5.4: Context continuity test
- Test sequence:
  1. user_id fixed, question: My name is Alice
  2. same user_id, question: What did I just say?
- Result:
  - CTX_ANSWER=Your previous message was: "My name is Alice"

### Exercise 5.5: Reliability conclusion
- Core production controls are implemented and validated locally.
- Current cloud blocker is Redis wiring on Render; once REDIS_URL is corrected, /ready should return 200.

## Final Summary
- Source code is production-oriented and passes local security/reliability tests.
- Render deployment is public and reachable.
- Remaining action before final grading: set correct Internal Redis URL and capture final screenshots.
