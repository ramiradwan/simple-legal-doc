import anyio
from pydantic import BaseModel, Field

# We import the base AuditEvent types, but drop MemoryQueueEventEmitter
from auditor.app.events.models import AuditEvent, AuditEventType
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor
from auditor.tests.semantic_audit.helpers import make_test_prompt

class DummyOutput(BaseModel):
    findings: list = Field(default_factory=list)

# ✅ Safe, non-blocking test emitter
class TestListEmitter:
    def __init__(self):
        self.events: list[AuditEvent] = []
        
    async def emit(self, event: AuditEvent) -> None:
        self.events.append(event)

async def _run_and_collect_events():
    emitter = TestListEmitter()

    executor = MockLLMExecutor(
        mode="success",
        output=DummyOutput(),
    )

    pipeline = build_ldvp_pipeline(
        executor=executor,
        prompt_factory=make_test_prompt,
    )

    await pipeline.run(
        content_derived_text="Stable short document text.",
        document_content={"schema_version": "1.0"},
        visible_text="Visible text",
        audit_id="audit-events-001",
        emitter=emitter,  # ✅ correct place
    )

    # We just return the list directly, completely avoiding the async hang
    return emitter.events

def test_ldvp_emits_one_event_per_pass():
    events = anyio.run(_run_and_collect_events)

    pass_events = [
        e for e in events
        if e.event_type == AuditEventType.SEMANTIC_PASS_COMPLETED
    ]

    assert len(pass_events) == 8
    assert [e.details["pass_id"] for e in pass_events] == [
        "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"
    ]