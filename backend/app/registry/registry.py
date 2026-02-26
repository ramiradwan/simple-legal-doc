"""  
Document template registry.  
  
This module defines the set of document templates that may be generated  
by the engine. Each template entry explicitly binds together:  
  
- a public template identifier (slug)  
- a semantic payload schema  
- a LaTeX template used for rendering  
- a human-readable description  
  
Templates must be registered here to be addressable via the API.  
"""  
  
from typing import Dict, Type  
  
from pydantic import BaseModel  
  
from app.schemas.decision import DecisionPayload  
from app.schemas.compliance_test import ComplianceTestPayload
  
  
class TemplateEntry(BaseModel):  
    """  
    Declarative description of a document template.  
  
    This structure defines the full contract required to generate a  
    document artifact from semantic input.  
    """  
  
    slug: str  
    schema: Type[BaseModel]  
    template_path: str  
    description: str  
  
    class Config:  
        arbitrary_types_allowed = True  
  
  
TEMPLATE_REGISTRY: Dict[str, TemplateEntry] = {  
    "etk-decision": TemplateEntry(  
        slug="etk-decision",  
        schema=DecisionPayload,  
        template_path="decision/main.tex.jinja",  
        description=(  
            "ETK-style formal response / decision document. "  
            "Includes financial tables, semantic status handling, "  
            "PDF/A-3b archival normalization, and cryptographic sealing."  
        ),  
    ),  
    "compliance-test-doc": TemplateEntry(
        slug="compliance-test-doc",
        schema=ComplianceTestPayload,
        template_path="compliance_test/main.tex.jinja",
        description=(
            "Compliance risk assessment memo. "
            "Test template designed to stress-test the LDVP empirical "
            "feedback loop. The open-ended justification and mitigation "
            "fields provide surface area for P7 Risk & Compliance findings "
            "when declared risk levels are inconsistent with accompanying "
            "reasoning."
        ),
    ),    
}  