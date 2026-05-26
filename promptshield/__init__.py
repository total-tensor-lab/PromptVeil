"""
PromptShield — privacy and safety middleware for LLM applications.

Quickstart::

    from promptshield import Shield

    shield = Shield(config_path="policy.yaml")
    safe_prompt = shield.scan(prompt)
"""

from .exceptions import ConfigurationError, PromptShieldError, SensitiveDataError
from .results import EntityResult, ScanResult
from .shield import Shield
from .vault import PseudonymVault

__all__ = [
    "Shield",
    "ScanResult",
    "EntityResult",
    "PseudonymVault",
    "SensitiveDataError",
    "ConfigurationError",
    "PromptShieldError",
]
__version__ = "0.2.0"
