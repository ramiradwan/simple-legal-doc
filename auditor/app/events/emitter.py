from __future__ import annotations  
  
from typing import Protocol  
  
from auditor.app.events.models import AuditEvent  
  
  
class AuditEventEmitter(Protocol):  
    """  
    Interface for broadcasting audit observations.  
  
    Implementations must be:  
    - non-blocking (or minimally blocking)  
    - fail-safe (emission failures must not crash the audit)  
    - observational only  
    """  
  
    async def emit(self, event: AuditEvent) -> None:  
        ...  
  
  
class NullEventEmitter:  
    """  
    A safe no-op emitter.  
  
    Used when:  
    - streaming is disabled  
    - running synchronous audits  
    - background jobs  
    - tests that do not care about events  
    """  
  
    async def emit(self, event: AuditEvent) -> None:  
        return  