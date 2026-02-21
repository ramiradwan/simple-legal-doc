def test_managed_identity_executor_path_without_api_keys(monkeypatch):  
    """  
    Guarantees:  
    - Azure Structured LLM Executor can be constructed using Managed Identity  
    - No API keys are required at initialization time  
    """  
  
    # Ensure no API keys exist  
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)  
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)  
  
    from auditor.app.semantic_audit.llm_executor import AzureStructuredLLMExecutor  
  
    # Minimal constructor arguments (no secrets)  
    executor = AzureStructuredLLMExecutor(  
        endpoint="https://example.openai.azure.com",  
        deployment="dummy-deployment",  
        api_version="2024-02-01",  
        base_system_text="System instructions",  
    )  
  
    # Construction success is the invariant  
    assert executor is not None  