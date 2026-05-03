"""
middleware sub-package — optional FastAPI/Starlette integration.

Requires ``pip install "promptshield[fastapi]"``.
"""

from .fastapi_middleware import PromptShieldMiddleware

__all__ = ["PromptShieldMiddleware"]
