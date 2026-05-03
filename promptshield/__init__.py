"""
PromptShield — privacy and safety middleware for LLM applications.

Quickstart::

    from promptshield import Shield

    shield = Shield(config_path="policy.yaml")
    safe_prompt = shield.scan(prompt)
"""

from .exceptions import ConfigurationError, PromptShieldError, SensitiveDataError
from .shield import Shield

__all__ = [
    "Shield",
    "SensitiveDataError",
    "ConfigurationError",
    "PromptShieldError",
]
__version__ = "0.1.0"
