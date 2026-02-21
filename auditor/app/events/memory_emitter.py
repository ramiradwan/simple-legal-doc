from __future__ import annotations  
  
import asyncio  
from typing import AsyncIterator  
  
from auditor.app.events.models import AuditEvent, AuditEventType  
from auditor.app.events.emitter import AuditEventEmitter  
  
  
class MemoryQueueEventEmitter(AuditEventEmitter):  
    """  
    In-memory async event emitter suitable for SSE streaming.  
  
    Properties:  
    - single-consumer  
    - non-blocking for the audit execution path  
    - deterministic ordering  
    - terminates cleanly on audit completion or failure  
    """  
  
    def __init__(self) -> None:  
        self._queue: asyncio.Queue[AuditEvent | None] = asyncio.Queue()  
        self._closed = False  
  
    async def emit(self, event: AuditEvent) -> None:  
        if self._closed:  
            return  
  
        try:  
            await self._queue.put(event)  
        except Exception:  
            # Fail-safe: never let observability break the audit  
            return  
  
        if event.event_type in {  
            AuditEventType.AUDIT_COMPLETED,  
            AuditEventType.AUDIT_FAILED,  
        }:  
            await self.close()  
  
    async def close(self) -> None:  
        if not self._closed:  
            self._closed = True  
            await self._queue.put(None)  
  
    async def stream(self) -> AsyncIterator[AuditEvent]:  
        """  
        Async generator yielding emitted events in order.  
        """  
        while True:  
            event = await self._queue.get()  
            if event is None:  
                break  
            yield event  