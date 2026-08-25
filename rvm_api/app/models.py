import threading
from typing import Any, Optional, Set

from fastapi import WebSocket
from pydantic import BaseModel


class RvmState(BaseModel):
    message: str = "Ready"
    points: int = 0
    last_event: Optional[str] = None
    last_code: Optional[str] = None
    last_ai: Optional[dict[str, Any]] = None
    last_rejection_reason: Optional[str] = None


state = RvmState()
event_lock = threading.Lock()

# WebSocket client registry
ws_clients: Set[WebSocket] = set()
