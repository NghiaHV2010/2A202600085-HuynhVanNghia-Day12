# Lab 12 - Complete Production Agent

This folder is the final production-ready submission for Day 12.

## What is included

- Multi-stage Dockerfile (non-root runtime)
- Docker Compose stack (agent + Redis)
- API key authentication
- Rate limiting (10 requests/minute per user)
- Monthly cost guard ($10 default budget)
- Redis-backed stateless conversation history
- Health and readiness endpoints
- Graceful shutdown handling
- Cloud deployment configs (Railway and Render)

## Project structure

```
06-lab-complete/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── auth.py
│   ├── rate_limiter.py
│   └── cost_guard.py
├── utils/
│   └── mock_llm.py
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── render.yaml
├── .env.example
├── .dockerignore
└── requirements.txt
```

## Run locally

```bash
# 1) Create environment file
cp .env.example .env

# 2) Start services
docker compose up --build

# 3) Health check
curl http://localhost:8000/health

# 4) Authenticated request
curl -X POST http://localhost:8000/ask \
     -H "X-API-Key: dev-key-change-me-in-production" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test-user", "question": "Hello"}'
```

## Deploy Railway

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway variables set REDIS_URL=redis://<your-redis-host>:6379/0
railway variables set REQUIRE_REDIS=true
railway up
railway domain
```

## Deploy Render

1. Push this folder to GitHub.
2. Create a new Blueprint service on Render.
3. Let Render load render.yaml.
4. Set secret env vars: AGENT_API_KEY and REDIS_URL.
5. Deploy and verify /health and /ready.

## Readiness self-check

```bash
python check_production_ready.py
```
