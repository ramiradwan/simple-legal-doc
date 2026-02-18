from pydantic import BaseModel, Field, ConfigDict  
  
  
class PromptFragment(BaseModel):  
    """  
    Immutable fragment of a semantic audit protocol prompt.  
  
    Prompt fragments are versioned, hashable, and auditable.  
    """  
  
    protocol_id: str = Field(  
        ...,  
        description="Protocol identifier (e.g., LDVP)",  
    )  
  
    protocol_version: str = Field(  
        ...,  
        description="Protocol version (e.g., 2.3)",  
    )  
  
    pass_id: str = Field(  
        ...,  
        description="Pass identifier this fragment applies to (e.g., P1)",  
    )  
  
    text: str = Field(  
        ...,  
        description="Prompt content",  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  