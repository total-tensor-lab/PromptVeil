"""
middleware sub-package — optional FastAPI/Starlette integration.

Requires ``pip install "promptveil[fastapi]"``.
"""

from .fastapi_middleware import PromptVeilMiddleware

__all__ = ["PromptVeilMiddleware"]
