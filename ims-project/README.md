# Incident Management System (IMS)

**Author:** Niharika | Infrastructure / SRE Intern Assignment — Zeotap

---

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLIENT / BROWSER                          │
│                     React + Vite (Port 3000)                      │
│          Dashboard │ Work Items │ Signal Tester │ Health           │
└───────────────────────────┬────────────────────────────────────────┘
                            │  HTTP / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Port 8000)                      │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐  │
│  │ /api/signals │   │/api/workitems│   │  /health  /ws/live    │  │
│  │  Rate-limited│   │  CRUD + RCA  │   │  health + WS stream   │  │
│  └──────┬───────┘   └──────┬───────┘   └───────────────────────┘  │
│         │                  │                                        │
│         ▼                  ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           IN-MEMORY BOUNDED QUEUE (asyncio.Queue)           │   │
│  │       Cap: 50,000 signals │ Non-blocking put (drop-on-full) │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              SIGNAL PROCESSOR (Async Worker)                │   │
│  │                                                             │   │
│  │  1. Persist raw signal → MongoDB (with retry)               │   │
│  │  2. Debounce window (10s / 100 signals per component_id)    │   │
│  │  3. Strategy Pattern → AlertStrategyFactory → P0/P1/P2      │   │
│  │  4. Create Work Item → PostgreSQL (transactional)           │   │
│  │  5. Invalidate Redis cache                                   │   │
│  └──────┬────────────────┬────────────────────────────────────┘   │
│         │                │                                         │
└─────────┼────────────────┼─────────────────────────────────────────┘
          │                │
          ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   MongoDB    │  │  PostgreSQL  │  │    Redis     │
│  (Data Lake) │  │(Source of    │  │  (Hot Cache) │
│              │  │   Truth)     │  │              │
│ Raw signals  │  │ Work Items   │  │ Dashboard    │
│ Audit log    │  │ RCA records  │  │ state (TTL)  │
│ Queryable    │  │ Transactional│  │ Invalidated  │
│ by component │  │ state machine│  │ on writes    │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Tech Stack Rationale

| Layer | Technology | Why |
|-------|-----------|-----|
| **API** | FastAPI + uvicorn | Async-native, high throughput, auto OpenAPI docs |
| **Queue** | `asyncio.Queue` (bounded) | In-process, zero-latency, natural backpressure |
| **Source of Truth** | PostgreSQL + SQLAlchemy async | ACID transactions for Work Items and RCA |
| **Data Lake** | MongoDB (Motor) | Schema-flexible, high-write, queryable raw signals |
| **Cache** | Redis | Sub-millisecond dashboard state, TTL-based invalidation |
| **Frontend** | React + Vite | SPA with real-time WebSocket updates |
| **Rate Limiting** | slowapi | Per-IP rate limiting on ingestion endpoints |
| **Retry Logic** | tenacity | Exponential backoff on all DB writes |

---

## Design Patterns Used

### 1. Strategy Pattern — `services/alerting.py`
Different component failures trigger different alerting logic:
- `P0CriticalAlert` → RDBMS: PagerDuty + Slack + Email, immediate escalation
- `P1HighAlert` → API / MCP Host / Queue: Slack + Email, 15-min escalation
- `P2MediumAlert` → Cache / NoSQL: Slack only, 1-hour window

`AlertStrategyFactory` maps `ComponentType → Strategy` — adding a new component type requires only adding a new strategy class and a mapping entry, with zero changes to existing code.

### 2. State Pattern — `services/state_machine.py`
Manages the Work Item lifecycle:
```
OPEN → INVESTIGATING → RESOLVED → CLOSED
         ↑_____________↑  (reopen if fix didn't hold)
```
Each state class encapsulates its own allowed transitions. The `CLOSED` state is terminal. **RESOLVED → CLOSED is guarded**: the system rejects the transition if no RCA has been submitted.

---

## How Backpressure is Handled

The system uses a **bounded in-memory queue** (`asyncio.Queue(maxsize=50_000)`) as the central buffer between the HTTP ingestion layer and the persistence workers.

**Key design decisions:**

1. **Non-blocking `put_nowait`**: The ingestion API endpoint never blocks waiting for the queue. When the queue is full, signals are **dropped** (not blocked), and a warning is logged. This prevents the HTTP server from becoming unresponsive under extreme load.

2. **Why drop instead of block?** Blocking would cause the FastAPI event loop to stall, cascading failures to all concurrent requests. Dropping with metrics allows the system to remain available and self-heal.

3. **Queue cap at 50,000**: At 10,000 signals/sec, this gives a 5-second buffer before dropping begins. Enough time for transient slowdowns in MongoDB/PostgreSQL to recover.

4. **Drop metrics**: `total_dropped` and `drop_rate_pct` are exposed on `/api/v1/signals/queue/stats` and logged every 5 seconds, so ops teams can observe and alert on drop rates.

5. **Rate limiting** (`slowapi`): The ingestion endpoint is rate-limited to 10,000 requests/minute per IP, preventing a single rogue producer from filling the queue alone.

---

## Setup Instructions

### Prerequisites
- Docker & Docker Compose (v2+)
- Git

### 1. Clone & Configure
```bash
git clone <your-repo-url>
cd ims-project

# Copy env file
cp backend/.env.example backend/.env
```

### 2. Start with Docker Compose
```bash
docker-compose up --build
```

This starts:
- **PostgreSQL** on port `5432`
- **MongoDB** on port `27017`
- **Redis** on port `6379`
- **Backend API** on port `8000`
- **Frontend** on port `3000`

### 3. Access the Application
| Service | URL |
|---------|-----|
| Frontend Dashboard | http://localhost:3000 |
| Backend API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

### 4. Run Failure Simulation
```bash
# Install simulation script dependencies
pip install httpx

# Run all scenarios (sends ~1000 signals, triggers debounce, creates work items)
python scripts/simulate_failure.py --scenario all

# Or run specific scenarios
python scripts/simulate_failure.py --scenario rdbms
python scripts/simulate_failure.py --scenario cascade
```

### 5. Run Tests
```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

### 6. Local Development (without Docker)
```bash
# Start databases only
docker-compose up postgres mongo redis -d

# Backend
cd backend
cp .env.example .env
# Edit .env: change hosts to 'localhost'
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## API Reference

### Signal Ingestion
```
POST /api/v1/signals          - Ingest single signal (202 Accepted)
POST /api/v1/signals/batch    - Ingest up to 500 signals
GET  /api/v1/signals/{work_item_id} - Get raw signals for a work item
GET  /api/v1/signals/queue/stats    - Queue metrics
```

### Work Items
```
GET    /api/v1/workitems              - List all work items (filterable)
GET    /api/v1/workitems/stats        - Dashboard stats
GET    /api/v1/workitems/{id}         - Get work item detail
PATCH  /api/v1/workitems/{id}/status  - Update status
POST   /api/v1/workitems/{id}/rca     - Submit RCA
```

### System
```
GET /health    - Health check for all services
WS  /ws/live   - WebSocket for real-time updates
```

---

## Debounce Logic

When 100+ signals arrive for the same `component_id` within a 10-second window:
1. All signals are stored raw in MongoDB individually
2. Only **one** Work Item is created in PostgreSQL
3. All 100 signals are linked to that Work Item via `work_item_id`
4. Signals after the threshold continue to increment the `signal_count` counter

This prevents alert storms and duplicate Work Items for the same underlying failure.

---

## MTTR Calculation

MTTR is automatically calculated when the RCA is submitted:
```
MTTR (minutes) = (incident_end - incident_start).total_seconds() / 60
```

The `incident_start` is provided by the responder in the RCA form (the time the first alert was received), and `incident_end` is when the fix was confirmed stable.

---

## Non-Functional Items (Bonus)

1. **Retry Logic** (`tenacity`): All DB writes (MongoDB + PostgreSQL) have exponential backoff retry (3 attempts, 0.5–5s wait).

2. **Observability**: Throughput metrics (signals/sec) logged every 5 seconds. `/health` endpoint checks all services.

3. **Rate Limiting** (`slowapi`): 10,000/min on ingestion, 1,000/min on management APIs.

4. **Redis Cache Invalidation**: Cache keys are pattern-invalidated on every state change, ensuring no stale reads on the dashboard.

5. **WebSocket Live Updates**: Frontend receives real-time queue stats without polling.

6. **Concurrency**: `asyncio`-native throughout — no threading, no race conditions. SQLAlchemy `begin_nested()` used for nested transactions.

7. **Health Check**: `/health` verifies connectivity to PostgreSQL, MongoDB, and Redis before reporting healthy.

---

## Prompts / AI Usage

All AI prompts and planning documents used during development are in [`docs/PROMPTS.md`](docs/PROMPTS.md).
