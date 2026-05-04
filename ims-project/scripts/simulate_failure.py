#!/usr/bin/env python3
"""
Mock Failure Event Simulation Script
Simulates a realistic RDBMS outage cascade across the stack.

Usage:
    python scripts/simulate_failure.py [--host http://localhost:8000] [--scenario all]

Scenarios:
    rdbms     - Primary database failure (P0)
    mcp       - MCP Host degradation (P1)
    cache     - Distributed cache failure (P2)
    cascade   - RDBMS → API → Queue cascade
    all       - Run all scenarios sequentially
"""

import asyncio
import httpx
import argparse
import time
import json
from datetime import datetime


BASE_URL = "http://localhost:8000"
BATCH_ENDPOINT = "/api/v1/signals/batch"
SINGLE_ENDPOINT = "/api/v1/signals"


async def send_batch(client: httpx.AsyncClient, signals: list, label: str):
    """Send a batch of signals and report result."""
    chunk_size = 500
    total_sent = 0
    for i in range(0, len(signals), chunk_size):
        chunk = signals[i:i + chunk_size]
        try:
            resp = await client.post(BATCH_ENDPOINT, json=chunk, timeout=30)
            data = resp.json()
            total_sent += data.get("accepted", 0)
            print(f"  ✓ [{label}] Chunk {i//chunk_size + 1}: {data.get('accepted')} accepted, {data.get('dropped')} dropped | Queue: {data.get('queue_size')}")
        except Exception as e:
            print(f"  ✗ [{label}] Error: {e}")
    return total_sent


async def scenario_rdbms_outage(client: httpx.AsyncClient):
    """Simulate RDBMS primary node failure — 200 signals over 2 rounds."""
    print("\n🔴 SCENARIO: RDBMS Primary Outage (P0)")
    print("   Sending 200 signals for RDBMS_PRIMARY — expect 1 P0 Work Item after debounce")

    signals = [
        {
            "component_id": "RDBMS_PRIMARY",
            "component_type": "RDBMS",
            "signal_type": "CONNECTION_REFUSED",
            "message": f"Primary DB node refused connection (attempt {i+1})",
            "metadata": {"host": "db-primary-01", "port": 5432, "attempt": i + 1},
            "timestamp": datetime.utcnow().isoformat(),
        }
        for i in range(200)
    ]
    sent = await send_batch(client, signals, "RDBMS")
    print(f"   → Total accepted: {sent}")


async def scenario_mcp_degradation(client: httpx.AsyncClient):
    """Simulate MCP Host latency degradation — 150 signals."""
    print("\n🟠 SCENARIO: MCP Host Latency Spike (P1)")
    print("   Sending 150 signals for MCP_HOST_01 — expect 1 P1 Work Item")

    signals = [
        {
            "component_id": "MCP_HOST_01",
            "component_type": "MCP_HOST",
            "signal_type": "LATENCY_SPIKE",
            "message": f"Request latency {300 + i * 5}ms — exceeds 200ms SLA",
            "metadata": {"latency_ms": 300 + i * 5, "endpoint": "/mcp/v1/process"},
        }
        for i in range(150)
    ]
    sent = await send_batch(client, signals, "MCP_HOST")
    print(f"   → Total accepted: {sent}")


async def scenario_cache_failure(client: httpx.AsyncClient):
    """Simulate cache cluster failure — 120 signals."""
    print("\n🟡 SCENARIO: Distributed Cache Failure (P2)")
    print("   Sending 120 signals for CACHE_CLUSTER_01")

    signals = [
        {
            "component_id": "CACHE_CLUSTER_01",
            "component_type": "CACHE",
            "signal_type": "HEALTH_FAIL",
            "message": f"Cache node {i % 4} health check failed — eviction in progress",
            "metadata": {"node_id": i % 4, "cluster": "cache-cluster-01"},
        }
        for i in range(120)
    ]
    sent = await send_batch(client, signals, "CACHE")
    print(f"   → Total accepted: {sent}")


async def scenario_cascade(client: httpx.AsyncClient):
    """
    Full cascade: RDBMS outage causes API errors → Queue backlogs.
    This tests that each component gets its own independent Work Item.
    """
    print("\n⚡ SCENARIO: Multi-component Cascade")
    print("   RDBMS → API → Queue cascade — expect 3 separate Work Items")

    all_signals = []

    # Phase 1: RDBMS goes down
    all_signals += [
        {
            "component_id": "RDBMS_SECONDARY_01",
            "component_type": "RDBMS",
            "signal_type": "CONNECTION_REFUSED",
            "message": f"Secondary DB also down — no failover available [{i}]",
            "metadata": {"phase": "1_db_outage"},
        }
        for i in range(100)
    ]

    # Phase 2: APIs start failing
    all_signals += [
        {
            "component_id": "API_GATEWAY_01",
            "component_type": "API",
            "signal_type": "TIMEOUT",
            "message": f"API request timeout — downstream DB unavailable [{i}]",
            "metadata": {"phase": "2_api_impact", "status_code": 503},
        }
        for i in range(100)
    ]

    # Phase 3: Async queue backs up
    all_signals += [
        {
            "component_id": "ASYNC_QUEUE_MAIN",
            "component_type": "ASYNC_QUEUE",
            "signal_type": "ERROR",
            "message": f"Queue consumer failed — DB write timeout [{i}]",
            "metadata": {"phase": "3_queue_backlog", "queue_depth": i * 100},
        }
        for i in range(100)
    ]

    # Shuffle to simulate real interleaving
    import random
    random.shuffle(all_signals)

    sent = await send_batch(client, all_signals, "CASCADE")
    print(f"   → Total accepted: {sent}")


async def wait_and_check(client: httpx.AsyncClient):
    """Wait for processor to catch up, then show work items created."""
    print("\n⏳ Waiting 5 seconds for async processor to catch up...")
    await asyncio.sleep(5)

    try:
        resp = await client.get("/api/v1/workitems")
        data = resp.json()
        items = data.get("work_items", [])
        print(f"\n📋 Work Items Created: {len(items)}")
        for item in items[:10]:
            print(f"   [{item['priority']}] {item['component_id']} | {item['status']} | {item['signal_count']} signals")

        stats = await client.get("/api/v1/workitems/stats")
        s = stats.json()
        print(f"\n📊 Dashboard Stats:")
        print(f"   Open: {s.get('total_open')} | Investigating: {s.get('total_investigating')} | P0: {s.get('p0_count')} | P1: {s.get('p1_count')}")
    except Exception as e:
        print(f"Could not fetch results: {e}")


async def main():
    parser = argparse.ArgumentParser(description="IMS Failure Simulation Script")
    parser.add_argument("--host", default=BASE_URL, help="Backend base URL")
    parser.add_argument("--scenario", default="all",
                        choices=["rdbms", "mcp", "cache", "cascade", "all"],
                        help="Which scenario to run")
    args = parser.parse_args()

    global BASE_URL
    BASE_URL = args.host

    print("=" * 60)
    print("  IMS Failure Simulation Script")
    print(f"  Target: {args.host}")
    print(f"  Scenario: {args.scenario}")
    print("=" * 60)

    async with httpx.AsyncClient(base_url=args.host) as client:
        # Health check first
        try:
            health = await client.get("/health", timeout=5)
            print(f"\n✅ Backend health: {health.json().get('status')}")
        except Exception:
            print("❌ Backend not reachable. Is it running?")
            return

        if args.scenario in ("rdbms", "all"):
            await scenario_rdbms_outage(client)
            if args.scenario == "all":
                await asyncio.sleep(1)

        if args.scenario in ("mcp", "all"):
            await scenario_mcp_degradation(client)
            if args.scenario == "all":
                await asyncio.sleep(1)

        if args.scenario in ("cache", "all"):
            await scenario_cache_failure(client)
            if args.scenario == "all":
                await asyncio.sleep(1)

        if args.scenario in ("cascade", "all"):
            await scenario_cascade(client)

        await wait_and_check(client)

    print("\n✅ Simulation complete!")


if __name__ == "__main__":
    asyncio.run(main())
