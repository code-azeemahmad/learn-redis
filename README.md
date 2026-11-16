# Learn Redis: From Fundamentals to Production SaaS Architecture

A hands-on, production-grade guide and reference implementation for **Redis** with **Python**, **FastAPI**, **PostgreSQL**, **Qdrant Vector DB**, and **Docker**.

This repository progresses from basic key-value operations to high-throughput SaaS caching patterns, background job queuing, multi-tier AI semantic caching, and enterprise-grade production hardening (TLS, ACL, memory limits, and persistence).

---

## Architecture Overview

```
                                      +-----------------------------------------------+
                                      |                 Client Layer                  |
                                      |   Browser / Frontend / API Gateway / cURL     |
                                      +-----------------------+-----------------------+
                                                              |
                                                              v
+-------------------------------------------------------------+--------------------------------------------------------------+
|                                                   FastAPI Microservices                                                    |
|                                                                                                                            |
|   +--------------------------+    +-----------------------------+    +-------------------------------------------------+   |
|   |      redis-fastapi       |    |   fastapi-background-jobs   |    |                fastapi-llm-cache                |   |
|   | - Cache-aside / Inval.   |    | - Redis Queue (RQ) Worker   |    | - Exact Match L1 (Redis)                        |   |
|   | - Distributed Locks      |    | - Background Email Tasks    |    | - Semantic Vector L2 (Qdrant)                   |   |
|   | - Cookie Auth & Sessions |    | - Queue Monitoring          |    | - Durable Storage L3 (PostgreSQL)               |   |
|   | - Lua Script Rate Limits |    +--------------+--------------+    | - Local LLM Inference (Ollama)                  |   |
|   +------------+-------------+                   |                   +------------------------+------------------------+   |
+----------------|---------------------------------|--------------------------------------------|----------------------------+
                 |                                 |                                            |
                 v                                 v                                            v
+----------------------------------------------------------------------------------------------------------------------------+
|                                                    Data & Cache Storage                                                    |
|                                                                                                                            |
|   +--------------------------+    +-----------------------------+    +-------------------------------------------------+   |
|   |          Redis           |    |         PostgreSQL          |    |                     Qdrant                      |   |
|   | - In-memory L1 Cache     |    | - Relational Source of Truth|    | - Vector Similarity Search                      |   |
|   | - Session Store          |    | - Users & Orders            |    | - 768-dim Dense Embeddings                      |   |
|   | - Rate Limit Counters    |    | - Historical LLM Prompts    |    | - Rebuildable from PostgreSQL                   |   |
|   +--------------------------+    +-----------------------------+    +-------------------------------------------------+   |
+----------------------------------------------------------------------------------------------------------------------------+
```

---

## Repository Structure

```
learn-redis/
├── README.md                     # Comprehensive project documentation
├── LICENSE                       # MIT License (2026 code-azeemahmad)
├── redis-roadmap.md              # 7-phase, 37-lesson curriculum roadmap
├── compose.yml                   # Development stack (Redis, PostgreSQL, pgAdmin, Qdrant)
├── requirements.txt              # Core project dependencies
├── benchmark.py                  # Standalone HTTP benchmarking script
├── notes.txt                     # Development scratchpad & shell commands
│
├── redis/
│   └── redis.conf                # Baseline development Redis configuration
│
├── redis-python/                 # Phase 1: Pure Python & Async Redis
│   └── main.py                   # Async connection pool, TTL, basic CRUD operations
│
├── redis-fastapi/                # Phase 2-4: Enterprise SaaS FastAPI Backend
│   ├── app/
│   │   ├── main.py               # Application entrypoint & lifespan management
│   │   ├── database.py           # Async SQLAlchemy engine & session factory
│   │   ├── dependencies.py       # FastAPI dependency injection for Redis & DB
│   │   ├── models.py             # SQLAlchemy models (User, Order)
│   │   ├── schemas.py            # Pydantic request/response schemas
│   │   ├── swagger_dark.py       # Custom dark-themed Swagger UI
│   │   ├── routers/
│   │   │   ├── auth.py           # Session auth, cookies, logout, token revocation
│   │   │   ├── cache.py          # Cache stats, health, and manual invalidation
│   │   │   ├── dashboard.py      # Database aggregation caching (Order analytics)
│   │   │   ├── products.py       # CRUD with Cache-Aside, Locks, and Null caching
│   │   │   └── users.py          # User management and profile caching
│   │   ├── services/
│   │   │   ├── cache_warming.py  # Startup cache warming service
│   │   │   ├── rate_limiter.py   # Lua-scripted atomic fixed-window rate limiter
│   │   │   ├── redis_service.py  # Asynchronous Redis service wrapper
│   │   │   └── session_service.py# Session ID generation, verification, and revocation
│   │   └── utils/
│   │       ├── cache_keys.py     # Standardized cache key generators
│   │       └── serializers.py    # Robust JSON serialization helpers
│   ├── benchmark.py              # Cache hit vs miss latency benchmark
│   ├── seed_orders.py            # Seed realistic multi-tenant order records
│   └── seed_users.py             # Seed user accounts with hashed credentials
│
├── fastapi-background-jobs/      # Phase 4: Asynchronous Task Queues with RQ
│   ├── compose.yaml              # Dedicated worker and Redis stack
│   ├── requirements.txt          # RQ and worker dependencies
│   ├── .env.sample               # Environment configuration template
│   └── app/
│       ├── main.py               # Enqueue endpoints and job status check
│       └── jobs/
│           └── email_jobs.py     # Background worker task definitions
│
├── fastapi-llm-cache/            # Phase 4: Multi-Tier AI Semantic Caching
│   ├── db.md                     # Multi-tier vector and persistence architecture
│   ├── requirements.txt          # Dependencies (FastAPI, Redis, SQLAlchemy, httpx)
│   ├── .env.sample               # Environment variables template
│   └── app/
│       ├── main.py               # Chat inference endpoints and cache statistics
│       ├── config.py             # Centralized settings & connection string masking
│       ├── database.py           # PostgreSQL async connection for LLM queries
│       ├── models.py             # LLMQuery source-of-truth table
│       ├── services/
│       │   ├── embedding_service.py # Ollama nomic-embed-text (768-dim embeddings)
│       │   ├── llm_service.py    # Multi-tier orchestrator (L1 -> L2 -> L3)
│       │   └── qdrant_service.py # Native REST integration with Qdrant vector DB
│       └── utils/
│           └── cache_keys.py     # Canonical prompt hashing for exact matches
│
└── redis-production/             # Phase 5: Production-Hardened Redis Deployment
    ├── compose.yaml              # Production Docker Compose specification
    ├── notes.txt                 # TLS generation and validation notes
    ├── .env.sample               # Production environment variable template
    ├── .gitignore                # Protects production certificates and secrets
    └── redis/
        ├── redis.conf            # Memory limits, eviction policies, TLS, and ACL
        ├── users.acl             # Access Control Lists with least privilege
        └── certs/                # TLS Certificate Authority, server certs, and keys
```

---

## Projects & Implementations

### 1. `redis-fastapi`: Enterprise SaaS Caching & Security
A full-featured FastAPI backend illustrating real-world SaaS caching patterns:
- **Cache-Aside Pattern**: Checks Redis before hitting PostgreSQL; populates Redis upon cache misses.
- **Cache Stampede Prevention**: Employs distributed mutex locks so only one concurrent request queries the database while other requests wait.
- **Cache Penetration Protection**: Caches empty sentinel results (`null`) with short TTLs to protect against nonexistent IDs.
- **Cache Invalidation & TTL Jitter**: Systematic key invalidation upon mutations (`POST`, `PUT`, `DELETE`) with pseudo-random jitter added to TTLs to avoid simultaneous expiration.
- **Database Aggregation Caching**: Pre-calculated metrics for `GET /dashboard/stats` cached with compound tenant/date keys.
- **Atomic Lua Rate Limiting**: Token-bucket / fixed-window rate limiter evaluated inside Redis with Lua scripts, returning `HTTP 429 Too Many Requests` when limits are exceeded.
- **Server-Side Session Management**: Secure HTTP-only cookies storing opaque session UUIDs mapped to Redis session records with automatic sliding expiration and instant logout/revocation.

### 2. `fastapi-llm-cache`: Multi-Tier AI Semantic Caching
Caches expensive Large Language Model (LLM) responses across three layers:
- **Layer 1 (L1) — Redis Exact Match Cache**: SHA-256 canonical hash of prompt, system prompt, and temperature. Returns responses in **< 1ms**.
- **Layer 2 (L2) — Qdrant Semantic Vector Search**: Embeds user query using Ollama's `nomic-embed-text` (768 dimensions) and queries Qdrant for semantic cosine similarity ($\ge 0.85$). Serves rephrased queries in **~15ms** without model inference.
- **Layer 3 (L3) — PostgreSQL & Ollama Inference**: When both caches miss, executes local inference via `llama3.1:8b`, writes the record durably to PostgreSQL (Source of Truth), indexes the vector point in Qdrant, and sets L1 in Redis.
- **Index Rebuildability**: Includes `POST /cache/rebuild` to demonstrate that the entire vector index can be regenerated from the PostgreSQL source of truth at any time.

### 3. `fastapi-background-jobs`: Task Queues with RQ
Decouples slow tasks (email delivery, report compilation) from the synchronous HTTP request cycle:
- **FastAPI Endpoint**: Quickly enqueues jobs to Redis via `rq.Queue` and immediately returns job IDs to the caller (`HTTP 202 Accepted`).
- **Independent RQ Worker**: Consumes jobs asynchronously in the background.
- **Job Status Polling**: Endpoints to monitor job progress (`queued`, `started`, `finished`, `failed`).

### 4. `redis-production`: Hardened Production Deployment
Implements security and resilience best practices for production Redis:
- **TLS/SSL Encryption**: All traffic encrypted via TLS 1.3 (`tls-port 6379`, `port 0` disables unencrypted plain text).
- **Access Control Lists (ACL)**: 
  - `user default off` (disables default unauthenticated access).
  - Dedicated `fastapi` user with selective command sets and key prefixes.
  - Dedicated `healthcheck` user restricted exclusively to `+ping`.
- **Memory Management & Eviction**:
  - `maxmemory 256mb` capped with headroom inside container's `mem_limit: 384m`.
  - `maxmemory-policy allkeys-lru` with `lazyfree-lazy-eviction yes`.
- **Cache-Only vs. Hybrid Persistence**: Clean configuration toggles between pure in-memory cache (`save ""`, `appendonly no`) and durable persistence (`appendonly yes`, `appendfsync everysec`, `aof-use-rdb-preamble yes`).
- **Network Isolation**: Zero published host ports; services communicate over internal Docker bridge networks.

---

## Quickstart & Setup

### Prerequisites
- [Docker](https://docs.docker.com/engine/install/) & [Docker Compose](https://docs.docker.com/compose/)
- [Python 3.10+](https://www.python.org/)
- Optional for LLM caching: [Ollama](https://ollama.com/) with models:
  ```bash
  ollama pull llama3.1:8b
  ollama pull nomic-embed-text:latest
  ```

### 1. Clone & Set Up Python Environment
```bash
git clone https://github.com/code-azeemahmad/learn-redis.git
cd learn-redis

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Launch the Development Stack
Start Redis, PostgreSQL, pgAdmin, and Qdrant in the background:
```bash
docker compose up -d
```

Verify running services:
```bash
docker compose ps
```
| Service | Container Name | Port Mapping | Purpose |
| :--- | :--- | :--- | :--- |
| **Redis** | `redis-dev` | `127.0.0.1:6379` | Development caching instance |
| **PostgreSQL** | `postgres-db` | `127.0.0.1:5432` | Relational source of truth (`saas_db`) |
| **pgAdmin** | `pgadmin` | `127.0.0.1:5050` | Database management UI (`admin@example.com` / `admin`) |
| **Qdrant** | `qdrant-db` | `127.0.0.1:6333` | Vector database REST / gRPC |

---

## Running the Applications

### Running `redis-fastapi`
```bash
cd redis-fastapi

# 1. Seed demo database
python seed_users.py
python seed_orders.py

# 2. Start the FastAPI server
uvicorn app.main:app --reload --port 8000
```
- Interactive API Docs (Dark Theme): [http://localhost:8000/docs](http://localhost:8000/docs)
- Benchmark Cache Latency:
  ```bash
  python benchmark.py
  ```

### Running `fastapi-llm-cache`
```bash
cd fastapi-llm-cache

# 1. Copy sample configuration
cp .env.sample .env
# Edit .env with your credentials

# 2. Run API server
uvicorn app.main:app --reload --port 8001
```
- API Documentation: [http://localhost:8001/docs](http://localhost:8001/docs)
- Test Exact vs Semantic Caching:
  ```bash
  # First request (LLM Inference - ~3-5s)
  curl -X POST http://localhost:8001/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt": "What is semantic caching in simple words?"}'

  # Identical request (Redis Exact Cache Hit - ~1ms)
  curl -X POST http://localhost:8001/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt": "What is semantic caching in simple words?"}'

  # Rephrased request (Qdrant Semantic Cache Hit - ~15ms)
  curl -X POST http://localhost:8001/chat \
    -H "Content-Type: application/json" \
    -d '{"prompt": "Explain semantic caching simply"}'
  ```

### Running `fastapi-background-jobs`
```bash
cd fastapi-background-jobs
cp .env.sample .env

# Terminal 1: Start API server
uvicorn app.main:app --reload --port 8002

# Terminal 2: Start RQ Worker
rq worker --with-scheduler
```
Enqueue a background email job:
```bash
curl -X POST "http://localhost:8002/register?email=user@example.com"
```

### Running `redis-production`
```bash
cd redis-production
cp .env.sample .env
# Populate secure passwords in .env

# Start hardened container
docker compose up -d

# Verify authenticated healthcheck
docker compose ps
```
Authenticate via TLS with `redis-cli`:
```bash
docker compose exec redis redis-cli \
  --tls \
  --cacert /usr/local/etc/redis/certs/ca.crt \
  --user fastapi \
  --pass "$FASTAPI_PASSWORD" \
  ping
# Output: PONG
```

---

## Caching Patterns Reference Guide

| Pattern / Strategy | Problem Addressed | Implementation Detail | Location |
| :--- | :--- | :--- | :--- |
| **Cache-Aside** | Minimizes database load for frequent reads | Application checks cache first; falls back to DB and writes back to cache. | `redis-fastapi/app/routers/products.py` |
| **Mutex Locking (Single-Flight)** | Prevents **Cache Stampede** when hot keys expire | Redis `SET ... NX EX` distributed lock ensures only one worker recomputes data. | `redis-fastapi/app/routers/products.py` |
| **Null Caching** | Prevents **Cache Penetration** on invalid IDs | Non-existent records are cached as `"null"` with a short 60s TTL. | `redis-fastapi/app/routers/products.py` |
| **TTL Jitter** | Avoids simultaneous expiration spikes | Adds random offset ($\pm 10\%$) to base TTL values. | `redis-fastapi/app/services/redis_service.py` |
| **Cache Warming** | Cold start latency after deployments | Preloads popular items into cache during FastAPI startup lifespan. | `redis-fastapi/app/services/cache_warming.py` |
| **Lua Rate Limiting** | DDoS protection and fair API usage | Atomic Redis Lua script checks and increments counters within a fixed window. | `redis-fastapi/app/services/rate_limiter.py` |
| **Semantic Caching** | Reduces expensive LLM inference costs | Vector embeddings + Cosine similarity search in Qdrant before invoking LLM. | `fastapi-llm-cache/app/services/llm_service.py` |

---

## Roadmap

This repository follows the structured 7-phase curriculum outlined in [`redis-roadmap.md`](redis-roadmap.md):
1. **Phase 1**: Redis Fundamentals & Local Development
2. **Phase 2**: Integrating Redis with FastAPI
3. **Phase 3**: Professional Caching Strategies
4. **Phase 4**: Redis in Real-World SaaS Applications
5. **Phase 5**: Production Redis Deployment
6. **Phase 6**: Monitoring and Performance
7. **Phase 7**: Final Production Project

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2026 **code-azeemahmad**.
