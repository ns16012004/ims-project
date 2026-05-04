# Prompts, Spec & Planning

> This document records the AI prompts, specs, and reasoning used while building the IMS.
> Required per assignment guidelines: "All markdowns and prompts used to create this repository should be checked in."

---

## Initial Spec Reading & Decomposition

**Prompt used:**
> "Read the assignment PDF. Decompose it into backend components, frontend components, design patterns required, and non-functional requirements."

**Output (my analysis):**

| Requirement | Implementation |
|-------------|----------------|
| High-throughput signal ingestion | `POST /api/v1/signals` with asyncio.Queue buffer |
| Burst handling (10k/sec) | Bounded queue with non-blocking put + drop-on-full |
| Debounce (100 signals / 10s → 1 work item) | `DebounceWindow` class in processor.py |
| NoSQL data lake | MongoDB via Motor (async) |
| RDBMS source of truth | PostgreSQL via SQLAlchemy async |
| Hot cache | Redis with TTL + pattern invalidation |
| Strategy pattern for alerts | `AlertStrategy` ABC + `AlertStrategyFactory` |
| State pattern for work item lifecycle | `WorkItemState` ABC + state map |
| RCA mandatory for CLOSE | Guard in state machine + service layer |
| MTTR calculation | `(incident_end - incident_start).total_seconds() / 60` |
| Rate limiting | slowapi on FastAPI |
| /health endpoint | Checks all 3 DBs + queue |
| Throughput metrics | `metrics_reporter()` async task, logs every 5s |
| React dashboard | Zustand store, Recharts, WebSocket |

---

## Architecture Decisions

### Why asyncio.Queue over Redis Stream / Kafka for the buffer?
**Prompt:** "Should the in-memory queue use asyncio.Queue or Redis Streams for the assignment?"

**Reasoning:** The assignment says "your system cannot crash if persistence layer is slow" — this is specifically about the in-memory buffer absorbing spikes. asyncio.Queue is sufficient for a single-node deployment (the assignment scope), has zero network latency, and requires no additional infrastructure. Redis Streams / Kafka would be the right choice in a multi-node production system.

### Why MongoDB for signals?
**Prompt:** "The assignment says 'Data Lake' for raw signals — what storage fits?"

**Reasoning:** MongoDB is schema-flexible (signals can carry arbitrary metadata), supports high write throughput, and allows querying by `component_id`, `work_item_id`, and time range via compound indexes. No schema migrations needed when signal metadata evolves.

### Why PostgreSQL for work items?
Work items and RCAs require ACID guarantees — specifically:
- State transitions must be atomic (OPEN → INVESTIGATING must not be partially applied)
- RCA submission must be atomic with work item update
- MTTR should be consistent with stored timestamps

SQLAlchemy async + `session.begin()` / `begin_nested()` handles this cleanly.

---

## Design Pattern Research

**Prompt:** "The assignment says 'Use the right Design Pattern' for alerting and state. Which ones?"

**Answer:**
- **Alerting → Strategy Pattern**: Different behaviors (alert channels, escalation paths) for the same action (fire alert). New component types can be added without modifying existing strategies.
- **Work Item lifecycle → State Pattern**: Each state (OPEN, INVESTIGATING, RESOLVED, CLOSED) is a class that knows its own valid transitions. This prevents invalid transitions at the type level, not just via if/else chains.

---

## Frontend Design Decisions

**Prompt:** "Design a dark-themed incident dashboard for an SRE tool. Prioritize information density over aesthetics."

**Choices:**
- IBM Plex Mono / IBM Plex Sans for terminal-like authenticity
- Dark theme (`#0a0c10` base) with red/orange/yellow priority indicators
- Recharts bar charts for status/priority overview
- Zustand for state (simpler than Redux, no boilerplate)
- React Router v6 for SPA routing
- react-hot-toast for non-blocking notifications

---

## Test Design

**Prompt:** "What unit tests are most important for this IMS?"

**Priority:**
1. State machine transitions — the core business rule preventing premature closure
2. RCA validation — mandatory field lengths, date ordering
3. Debounce window — correct accumulation, threshold detection, multi-component isolation

Integration tests (DB + API) were deprioritized given the 1-week deadline; unit tests cover the critical business logic.
