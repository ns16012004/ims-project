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
