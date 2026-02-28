"""  
Passive PII observability utility.  
  
This module performs minimal, illustrative pattern detection  
using a small set of transparent regexes.  
  
It is intentionally incomplete and non-exhaustive.  
  
Purpose:  
- Demonstrate data egress observability  
- Surface obvious cases during development  
- Support shadow-mode rollout patterns  
  
Non-goals:  
- Accurate PII detection  
- Regulatory compliance  
- Enforcement, masking, or trust decisions  
"""  
  
import re  
from typing import Any  
  
  
# Intentionally small, transparent pattern set.  
# These are NOT guarantees — only observability signals.  
PII_PATTERNS = {  
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  
    "ssn_us": r"\b\d{3}-\d{2}-\d{4}\b",  
    "credit_card": r"\b(?:\d{4}[ -]?){3}\d{4}\b",  
}  
  
  
# IMPORTANT:  
# This function is for observability only.  
# Callers MUST NOT make policy, trust, or enforcement decisions  
# based on its output.  
def scan_for_pii(data: Any) -> list[str]:  
    """  
    Recursively scan a data structure for potential PII patterns.  
  
    Returns:  
        A sorted list of detected PII type labels.  
        Empty list means nothing detected.  
    """  
    detected: set[str] = set()  
  
    def _scan(value: Any) -> None:  
        if isinstance(value, str):  
            for label, pattern in PII_PATTERNS.items():  
                if re.search(pattern, value):  
                    detected.add(label)  
  
        elif isinstance(value, dict):  
            for v in value.values():  
                _scan(v)  
  
        elif isinstance(value, (list, tuple, set)):  
            for item in value:  
                _scan(item)  
        # All other types intentionally ignored  
  
    _scan(data)  
    return sorted(detected)  