import asyncio
import time
import uuid
from typing import Any

from .models import event_lock, state, ws_clients


async def _broadcast(payload: dict):
    dead = []
    for ws in list(ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)


def register_accept(source: str = "ai", evidence: dict[str, Any] | None = None):
    code = uuid.uuid4().hex[:8].upper()
    evidence = evidence or {}
    with event_lock:
        state.points += 1
        state.message = "PET bottle accepted"
        state.last_event = time.strftime("%H:%M:%S")
        state.last_code = code
        state.last_ai = evidence if source == "ai" else state.last_ai
        state.last_rejection_reason = None
    asyncio.run(
        _broadcast(
            {
                "type": "accept",
                "code": code,
                "points": state.points,
                "source": source,
                "evidence": evidence,
            }
        )
    )
    return code


def register_reject(source: str = "ai", reason: str = "rejected", evidence: dict[str, Any] | None = None):
    evidence = evidence or {}
    with event_lock:
        state.message = "Rejected"
        state.last_event = time.strftime("%H:%M:%S")
        state.last_rejection_reason = reason
        if source == "ai":
            state.last_ai = evidence
    asyncio.run(
        _broadcast(
            {
                "type": "reject",
                "source": source,
                "reason": reason,
                "evidence": evidence,
            }
        )
    )
