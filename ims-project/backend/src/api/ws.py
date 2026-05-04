"""WebSocket endpoint for real-time dashboard updates."""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from ..core.queue import signal_queue

router = APIRouter()

# Connected WebSocket clients
_clients: set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected WS clients."""
    if not _clients:
        return
    data = json.dumps(message, default=str)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    _clients.add(websocket)
    logger.info(f"WS client connected. Total: {len(_clients)}")
    try:
        while True:
            # Send queue stats every 2 seconds as a heartbeat
            stats = signal_queue.get_stats()
            await websocket.send_text(json.dumps({"type": "stats", "data": stats}))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        _clients.discard(websocket)
        logger.info(f"WS client disconnected. Total: {len(_clients)}")
    except Exception as e:
        _clients.discard(websocket)
        logger.error(f"WS error: {e}")
