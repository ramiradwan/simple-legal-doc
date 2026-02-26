"""
Template discovery and schema introspection endpoints.

These endpoints expose the Document Engine's registered template
catalogue and the exact Pydantic-derived JSON schemas used for
payload validation. Both routes are read-only and operate entirely
from the in-process registry — no disk I/O or schema parsing occurs
at request time.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.registry.registry import TEMPLATE_REGISTRY

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TemplateListItem(BaseModel):
    slug: str
    description: str


class TemplateListResponse(BaseModel):
    templates: List[TemplateListItem]


# ---------------------------------------------------------------------------
# GET /templates
# ---------------------------------------------------------------------------


@router.get(  
    "",  
    response_model=List[TemplateListItem],  
    summary="List registered document templates",  
)  
def list_templates() -> List[TemplateListItem]:  
    """
    Return all templates currently registered in the Document Engine.

    The response is derived entirely from the in-memory registry and
    is effectively instantaneous. No filesystem access occurs.
    """
    return [  
        TemplateListItem(slug=entry.slug, description=entry.description)  
        for entry in TEMPLATE_REGISTRY.values()  
    ]  


# ---------------------------------------------------------------------------
# GET /schema/{slug}
# ---------------------------------------------------------------------------


@router.get(
    "/schema/{slug}",
    summary="Return the JSON schema for a document template",
)
def get_template_schema(slug: str) -> Dict[str, Any]:
    """
    Return the JSON schema derived from the Pydantic model used to
    validate payloads for the given template.

    The schema is generated via Pydantic's native model_json_schema()
    and therefore reflects the exact validation rules enforced during
    document generation, including field constraints and the
    additionalProperties: false boundary.

    The document_hash field is marked readOnly in the schema and must
    not be supplied by the caller.
    """
    entry = TEMPLATE_REGISTRY.get(slug)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{slug}' not found.",
        )

    schema = entry.schema.model_json_schema()

    # Surface the additionalProperties boundary explicitly so that
    # consuming clients understand the schema is closed.
    schema.setdefault("additionalProperties", False)

    return schema